#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Hollow Knight - TR dil paketi patcher.

Kullanicinin KENDI oyun dosyalarini yamalar; telifli dosya dagitmaz.
Yalnizca TR metin bloklarini (tr-veri/*.b64) ve yamalama mantigini tasir.

  python3 hk-tr-patch.py "<oyun klasoru>"            # yamala
  python3 hk-tr-patch.py "<oyun klasoru>" --dry-run  # sadece kontrol
  python3 hk-tr-patch.py "<oyun klasoru>" --geri-al  # orijinale don
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tempfile

import attrs
import UnityPy
from UnityPy.helpers import TypeTreeHelper
from UnityPy.streams import EndianBinaryWriter

BETIK = os.path.dirname(os.path.abspath(__file__))
VERI = os.path.join(BETIK, "tr-veri", "tr")
YEDEK_AD = ".tr-dil-paketi-yedek"
DOSYALAR = ("resources.assets", "globalgamemanagers")
DLL_ANAHTAR = "Managed/Assembly-CSharp.dll"
# Yamanin test edildigi Unity surumu (Hollow Knight 1.5.12620, Steam).
# Baska bir surumde yama uygulanmaz; --zorla ile asilabilir (riski size aittir).
DESTEKLENEN_UNITY = ("6000.0.61f1",)

ON_EK = re.compile(r"^([A-Z]{2,5}(?:_[A-Z]{2,5})?)_(.+)$")


def md5(yol):
    h = hashlib.md5()  # nosemgrep: python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5 -- yalnizca dosya kimligi/degisiklik tespiti, guvenlik amacli degil
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


OYUN_ADLARI = {
    "hollow_knight.exe", "hollow knight.exe", "hollow_knight.x86_64",
    "hollow_knight", "hollow knight",
}


def oyun_acik():
    """Sadece surec ADINA bakar; komut satiri argumanlari yanlis eslesmesin."""
    try:
        if os.name == "nt":
            cikti = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                                   capture_output=True, text=True).stdout
            adlar = [satir.split(",")[0].strip('"').lower() for satir in cikti.splitlines() if satir]
        else:
            cikti = subprocess.run(["ps", "-eo", "comm="], capture_output=True, text=True).stdout
            adlar = [satir.strip().lower() for satir in cikti.splitlines()]
        return any(ad in OYUN_ADLARI for ad in adlar)
    except Exception:
        return False


def oyun_ara():
    ev = os.path.expanduser("~")
    adaylar = []
    if os.name == "nt":
        for kok in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if kok:
                adaylar.append(os.path.join(kok, "Steam", "steamapps", "common", "Hollow Knight"))
        for harf in "CDEFGHIJK":
            adaylar.append(f"{harf}:\\SteamLibrary\\steamapps\\common\\Hollow Knight")
            adaylar.append(f"{harf}:\\Steam\\steamapps\\common\\Hollow Knight")
            adaylar.append(f"{harf}:\\Games\\Hollow Knight")
    else:
        for kok in (".local/share/Steam", ".steam/steam", ".steam/root",
                    ".var/app/com.valvesoftware.Steam/.local/share/Steam",
                    ".var/app/com.valvesoftware.Steam/data/Steam"):
            adaylar.append(os.path.join(ev, kok, "steamapps", "common", "Hollow Knight"))
    for a in adaylar:
        if os.path.isfile(os.path.join(a, "hollow_knight_Data", "resources.assets")):
            return a
    return None


def veri_dizini(baslangic):
    yol = os.path.abspath(baslangic)
    if os.path.basename(yol) == "hollow_knight_Data":
        return yol
    aday = os.path.join(yol, "hollow_knight_Data")
    if os.path.isdir(aday):
        return aday
    if os.path.isfile(os.path.join(yol, "resources.assets")):
        return yol
    raise SystemExit(f"HATA: hollow_knight_Data bulunamadi: {yol}")


def dil_tablolari(env):
    adlar = []
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        ad = obj.peek_name()
        if ad:
            adlar.append((ad, obj))

    onekler = {}
    for ad, obj in adlar:
        m = ON_EK.match(ad)
        if m:
            onekler.setdefault(m.group(1), []).append((m.group(2), obj))

    if not onekler:
        raise SystemExit("HATA: dil tablosu bulunamadi (TextAsset isimleri beklenmedik).\n"
                         "     Bu oyun surumu taninmiyor olabilir; hicbir dosya degistirilmedi.")

    temel = max(onekler, key=lambda k: (len(onekler[k]), k == "EN"))
    tablolar = {ad: obj for ad, obj in onekler[temel]}
    return temel, tablolar, onekler


def font_sec(env):
    fontlar, secilen = [], None
    for obj in env.objects:
        if obj.type.name != "Font":
            continue
        try:
            ad = obj.peek_name() or ""
        except Exception:
            ad = ""
        fontlar.append((ad, obj))
        if secilen is None and "notinter" in ad.lower():
            secilen = obj
    if secilen is None:
        for ad, obj in fontlar:
            if "inter" in ad.lower() or "arial" in ad.lower() or "dejavu" in ad.lower():
                secilen = obj
                break
    return secilen, fontlar


def kaynak_dosya(tablo, onekler, temel):
    for onek in ("KO", temel):
        for ad, obj in onekler.get(onek, []):
            if ad == tablo:
                return obj
    for onek in onekler:
        for ad, obj in onekler[onek]:
            if ad == tablo:
                return obj
    return None


def dogrula(veri, beklenen, tr_id, dosya_id):
    """Yazilan dosyalari yeniden acip kontrol eder."""
    env = UnityPy.load(os.path.join(veri, "resources.assets"))
    bulunan = {}
    idler = set()
    for obj in env.objects:
        idler.add(obj.path_id)
        if obj.type.name == "TextAsset":
            ad = obj.peek_name() or ""
            if ad.startswith("TR_"):
                bulunan[ad[3:]] = obj.read_typetree()["m_Script"]
    sorun = []
    if len(bulunan) != len(tr_id):
        sorun.append(f"TR obje sayisi {len(bulunan)} != {len(tr_id)}")
    for tablo, b64 in beklenen.items():
        if bulunan.get(tablo) != b64:
            sorun.append(f"TR_{tablo} icerigi farkli")

    g = UnityPy.load(os.path.join(veri, "globalgamemanagers"))
    for obj in g.objects:
        if obj.type.name != "ResourceManager":
            continue
        kayitlar = [k for k in obj.read_typetree()["m_Container"]
                    if str(k[0]).lower().startswith("languages/tr_")]
        if len(kayitlar) != len(tr_id):
            sorun.append(f"indeks {len(kayitlar)} != {len(tr_id)}")
        if any(k[1].get("m_FileID") != dosya_id for k in kayitlar):
            sorun.append("indeks m_FileID tutarsiz")
        if any(k[1].get("m_PathID") not in idler for k in kayitlar):
            sorun.append("indeks olu pathID iceriyor")
        break
    kapat(env, g)
    return sorun


def kapat(*envler):
    """UnityPy dosya taniticilarini kapatir (Windows'da dosya degistirmek icin sart)."""
    for env in envler:
        try:
            env.file.reader.dispose()
        except Exception:
            pass
        for f in list(getattr(env, "files", {}).values()):
            try:
                f.reader.dispose()
            except Exception:
                pass


def arac_yolu():
    ad = "enumpatch.exe" if os.name == "nt" else "enumpatch"
    for aday in (os.path.join(BETIK, "enumpatch", ad),
                 os.path.join(BETIK, "..", "enumpatch", ad),
                 os.path.join(BETIK, ad)):
        if os.path.isfile(aday):
            return os.path.abspath(aday)
    return None


def yedekle(yol, yedek_yol, yamali):
    """Orijinal (TR icermeyen) dosyayi yedekler.

    Kural dosyanin KENDISINE bakar, kayitlara degil:
    - Dosyada TR yamasi varsa yedege ASLA yazilmaz (yedek orijinalin kalmali).
      Yedek de yoksa uyari verilir: orijinal bu klasorde yok.
    - Dosya yamali degilse ve yedek yoksa ya da yedekten farkliysa (Steam guncellemesi
      sonrasi gibi) yedek yenilenir; boylece KALDIR eski surumun dosyalarini yeni
      surumun ustune yazmaz.
    Donus: yazdirilacak mesaj ya da None.
    """
    var = os.path.exists(yedek_yol)
    if yamali:
        if var:
            return None
        return "UYARI: dosyada TR yamasi var ama orijinal yedegi yok; yedeklenmedi"
    if not var:
        os.makedirs(os.path.dirname(yedek_yol), exist_ok=True)
        shutil.copy2(yol, yedek_yol)
        return "yedeklendi"
    if md5(yol) == md5(yedek_yol):
        return None
    shutil.copy2(yol, yedek_yol)
    return "yedek yenilendi (oyun dosyasi degismis)"


def dll_yamala(veri, yedek):
    """SupportedLanguages enum'ina TR ekler. Arac yoksa uyari verip devam eder."""
    dll = os.path.join(veri, "Managed", "Assembly-CSharp.dll")
    if not os.path.isfile(dll):
        print("  ! Assembly-CSharp.dll bulunamadi; dil listesine TR eklenemedi.")
        return False
    arac = arac_yolu()
    if arac is None:
        print("  ! enumpatch araci bulunamadi; dil listesine TR eklenemedi.")
        return False
    if os.name != "nt" and not os.access(arac, os.X_OK):
        try:
            os.chmod(arac, 0o755)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions -- calistirilabilir arac icin gerekli
        except OSError:
            pass

    yedek_dll = os.path.join(yedek, "Managed", "Assembly-CSharp.dll")
    on = subprocess.run([arac, "--check", dll], capture_output=True, text=True)
    dll_yamali = on.returncode == 0          # DLL'de TR zaten var mi?

    cikti = dll + ".tr-yeni"
    r = subprocess.run([arac, dll, cikti], capture_output=True, text=True)
    print("  " + (r.stdout or r.stderr).strip().replace("\n", "\n  "))
    if r.returncode == 0 and not os.path.isfile(cikti):
        # enumpatch "TR zaten var" dedi ve cikti yazmadi: DLL onceden yamali.
        # Basari saymadan once gercekten TR iceriyor mu diye dogrula.
        k = subprocess.run([arac, "--check", dll], capture_output=True, text=True)
        if k.returncode == 0:
            mesaj = yedekle(dll, yedek_dll, True)
            if mesaj:
                print(f"  {mesaj}: {DLL_ANAHTAR}")
            return True
        print("  ! DLL'de TR dil kodu dogrulanamadi.")
        return False
    if r.returncode != 0 or not os.path.isfile(cikti):
        if os.path.isfile(cikti):
            os.remove(cikti)          # yarim kalan (bos) ciktiyi oyun klasorunde birakma
        print("  ! DLL yamasi basarisiz; eski DLL korundu.")
        return False
    k = subprocess.run([arac, "--check", cikti], capture_output=True, text=True)
    if k.returncode != 0:
        os.remove(cikti)
        print("  ! DLL dogrulanamadi; eski DLL korundu.")
        return False
    mesaj = yedekle(dll, yedek_dll, dll_yamali)
    if mesaj:
        print(f"  {mesaj}: {DLL_ANAHTAR}")
    if not yeniden_adlandir(cikti, dll):
        os.remove(cikti)
        print("  ! DLL degistirilemedi (dosya kilitli); eski DLL korundu.")
        return False
    print("  yazildi: Managed/Assembly-CSharp.dll")
    return True


def yeniden_adlandir(kaynak, hedef, deneme=10):
    for i in range(deneme):
        try:
            os.replace(kaynak, hedef)
            return True
        except PermissionError:
            time.sleep(0.3)
    return False


def atomik_yaz(kaynak, hedef):
    gecici = hedef + ".tr-yeni"
    shutil.copy2(kaynak, gecici)
    if not yeniden_adlandir(gecici, hedef):
        os.remove(gecici)
        raise SystemExit(f"HATA: dosya degistirilemedi (baska program kullaniyor olabilir): {hedef}")


def tr_uygula(veri, dry_run, zorla=False):
    kaynak_assets = os.path.join(veri, "resources.assets")
    kaynak_ggm = os.path.join(veri, "globalgamemanagers")
    for yol in (kaynak_assets, kaynak_ggm):
        if not os.path.isfile(yol):
            raise SystemExit(f"HATA: dosya yok: {yol}")

    if oyun_acik() and not dry_run:
        raise SystemExit("HATA: oyun acik. Once Hollow Knight'i kapatin.")

    bloklar = {}
    for yol in glob.glob(os.path.join(VERI, "*.b64")):
        bloklar[os.path.basename(yol)[:-4]] = open(yol, encoding="utf-8").read()
    if not bloklar:
        raise SystemExit(f"HATA: TR verisi bulunamadi: {VERI}")

    print(f"TR veri blogu: {len(bloklar)} tablo")
    env = UnityPy.load(kaynak_assets)
    f = env.file
    surum = getattr(f, "unity_version", None) or getattr(f, "version", "?")
    print(f"Unity surumu: {surum}")
    if str(surum).strip() not in DESTEKLENEN_UNITY:
        if not zorla:
            raise SystemExit(
                f"HATA: desteklenmeyen Unity surumu: {surum}\n"
                f"     Yama yalnizca {', '.join(DESTEKLENEN_UNITY)} (Hollow Knight 1.5.12620) icin test edildi.\n"
                "     Hicbir dosya degistirilmedi. Yine de denemek icin --zorla kullanin (risk size aittir).")
        print(f"  ! UYARI: desteklenmeyen Unity surumu ({surum}); --zorla ile devam ediliyor.")

    temel, tablolar, onekler = dil_tablolari(env)
    print(f"Kaynak dil oneki: {temel} ({len(tablolar)} tablo)")
    print(f"Bulunan dil onekleri: {', '.join(sorted(onekler))}")

    eksik = sorted(set(tablolar) - set(bloklar))
    if eksik:
        print(f"  i TR verisi olmayan tablo ({len(eksik)}): {eksik[:5]}")

    # 1) font yedegi
    font, fontlar = font_sec(env)
    font_adi = None
    if font is None:
        print("  ! Turkce font bulunamadi; glifler bozuk gorunebilir.")
    else:
        font_id = font.path_id
        font_adi = font.peek_name()
        print(f"Font yedegi: {font_adi!r} (pathID {font_id}), toplam font {len(fontlar)}")
        for ad, obj in fontlar:
            t = obj.read_typetree()
            fb = t.get("m_FallbackFonts")
            if fb is None:
                continue
            if any(x.get("m_FileID") == 0 and x.get("m_PathID") == font_id for x in fb):
                continue
            fb.append({"m_FileID": 0, "m_PathID": font_id})
            t["m_FallbackFonts"] = fb
            if not dry_run:
                obj.save_typetree(t)

    # 2) TR tablolari
    mevcut = {}
    for obj in env.objects:
        if obj.type.name == "TextAsset" and (obj.peek_name() or "").startswith("TR_"):
            mevcut[obj.peek_name()[3:]] = obj

    yeni_id = max(f.objects) + 1
    tr_id = {}
    olusturulan = guncellenen = 0
    for tablo in tablolar:
        b64 = bloklar.get(tablo)
        if b64 is None:
            continue
        if tablo in mevcut:
            obj = mevcut[tablo]
            t = obj.read_typetree()
            if t.get("m_Script") != b64:
                t["m_Script"] = b64
                if not dry_run:
                    obj.save_typetree(t)
                guncellenen += 1
            tr_id[tablo] = obj.path_id
            continue
        sablon = kaynak_dosya(tablo, onekler, temel)
        if sablon is None:
            print(f"  ! {tablo}: sablon obje yok, atlandi")
            continue
        t = sablon.read_typetree()
        t["m_Name"] = "TR_" + tablo
        t["m_Script"] = b64
        w = EndianBinaryWriter(endian=sablon.reader.endian)
        TypeTreeHelper.write_typetree(t, sablon._get_typetree_node(), w, f)
        ham = w.bytes
        yeni = attrs.evolve(sablon, path_id=yeni_id, data=ham, byte_size=len(ham))
        if not dry_run:
            f.objects[yeni_id] = yeni
        tr_id[tablo] = yeni_id
        yeni_id += 1
        olusturulan += 1

    print(f"TR tablosu: {len(tr_id)} (yeni {olusturulan}, guncellenen {guncellenen})")
    if dry_run:
        print("\n(dry-run: hicbir dosya degistirilmedi)")
        return

    f.mark_changed()
    gecici = tempfile.mkdtemp(prefix="hk-tr-")
    env.save(out_path=gecici)

    # 3) globalgamemanagers indeksi
    genv = UnityPy.load(kaynak_ggm)
    gdosya = genv.file
    dosya_id = None
    for i, ext in enumerate(gdosya.externals):
        if os.path.basename(str(ext.path)).lower() == "resources.assets":
            dosya_id = i + 1          # m_FileID 0 = bu dosya
            break
    if dosya_id is None:
        raise SystemExit("HATA: globalgamemanagers icinde resources.assets referansi yok.")
    print(f"resources.assets -> m_FileID {dosya_id}")

    eklenen = silinen = 0
    ggm_yamali = False
    gecerli = set(tr_id.values())
    for obj in genv.objects:
        if obj.type.name != "ResourceManager":
            continue
        t = obj.read_typetree()
        kap = t["m_Container"]
        ggm_yamali = any(str(k[0]).lower().startswith("languages/tr_") for k in kap)
        yeni_kap = []
        for kayit in kap:
            ad = str(kayit[0])
            if ad.lower().startswith("languages/tr_") and kayit[1].get("m_PathID") not in gecerli:
                silinen += 1
                continue
            yeni_kap.append(kayit)
        mevcut_ad = {str(k[0]).lower() for k in yeni_kap}
        for tablo, pid in tr_id.items():
            ad = "languages/tr_" + tablo.lower()
            if ad in mevcut_ad:
                continue
            yeni_kap.append([ad, {"m_FileID": dosya_id, "m_PathID": pid}])
            eklenen += 1
        t["m_Container"] = yeni_kap
        obj.save_typetree(t)
        break
    else:
        raise SystemExit("HATA: ResourceManager bulunamadi.")
    print(f"indeks: {eklenen} eklendi, {silinen} eski kayit temizlendi")
    genv.save(out_path=gecici)

    # 4) gecici kopyayi dogrula
    sorunlar = dogrula(gecici, {k: v for k, v in bloklar.items() if k in tr_id}, tr_id, dosya_id)
    if sorunlar:
        shutil.rmtree(gecici, ignore_errors=True)
        raise SystemExit("HATA: dogrulama basarisiz, dosyalar degistirilmedi:\n  " + "\n  ".join(sorunlar))
    kapat(env, genv)
    print("dogrulama: gecti")

    # 5) yedek + atomik yaz
    yedek = os.path.join(veri, YEDEK_AD)
    os.makedirs(yedek, exist_ok=True)
    yamali_mi = {"resources.assets": bool(mevcut), "globalgamemanagers": ggm_yamali}
    for ad in DOSYALAR:
        mesaj = yedekle(os.path.join(veri, ad), os.path.join(yedek, ad), yamali_mi[ad])
        if mesaj:
            print(f"  {mesaj}: {ad}")
    yazilan = []
    try:
        for ad in DOSYALAR:
            atomik_yaz(os.path.join(gecici, ad), os.path.join(veri, ad))
            yazilan.append(ad)
            print(f"  yazildi: {ad}  ({os.path.getsize(os.path.join(veri, ad))} bayt)")
    except BaseException:
        # yarim kalan yazma: iki dosya birbiriyle uyumsuz kalmasin, yedekten geri al
        print("HATA: yazma sirasinda sorun; yazilan dosyalar yedekten geri aliniyor...")
        for ad in yazilan:
            kaynak = os.path.join(yedek, ad)
            try:
                if os.path.isfile(kaynak):
                    atomik_yaz(kaynak, os.path.join(veri, ad))
                    print(f"  geri alindi: {ad}")
                else:
                    print(f"  ! yedek yok, geri alinamadi: {ad} (KALDIR'i deneyin)")
            except BaseException:
                print(f"  ! geri alinamadi: {ad} (KALDIR'i deneyin)")
        shutil.rmtree(gecici, ignore_errors=True)
        raise

    dll_ok = dll_yamala(veri, yedek)

    md5ler = {ad: md5(os.path.join(veri, ad)) for ad in DOSYALAR}
    if dll_ok:
        md5ler[DLL_ANAHTAR] = md5(os.path.join(veri, "Managed", "Assembly-CSharp.dll"))
    with open(os.path.join(yedek, "tr-yama.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "surum": 1,
            "dll": dll_ok,
            "tablolar": sorted(tr_id),
            "m_FileID": dosya_id,
            "font": font_adi,
            "unity": str(surum),
            "md5": md5ler,
        }, fh, ensure_ascii=False, indent=1)
    shutil.rmtree(gecici, ignore_errors=True)
    if dll_ok:
        print("\nTAMAM. Oyunu acin -> SECENEKLER -> dil listesinde 'TR'.")
    else:
        print("\nUYARI: Metin tablolari yazildi, ama dil listesine 'TR' EKLENEMEDI")
        print("(Assembly-CSharp.dll yamalanamadi; yukaridaki hata mesajina bakin).")
        print("Oyunda TR secenegi gorunmeyebilir. KUR'u tekrar calistirabilir ya da")
        print("KALDIR ile her seyi geri alabilirsiniz.")
    return dll_ok


def geri_al(veri):
    yedek = os.path.join(veri, YEDEK_AD)
    if not os.path.isdir(yedek):
        raise SystemExit(f"HATA: yedek yok: {yedek}")
    if oyun_acik():
        raise SystemExit("HATA: oyun acik. Once Hollow Knight'i kapatin.")
    for ad in DOSYALAR:
        kaynak = os.path.join(yedek, ad)
        if not os.path.isfile(kaynak):
            print(f"  ! yedek yok, atlandi: {ad}")
            continue
        atomik_yaz(kaynak, os.path.join(veri, ad))
        print(f"  geri yuklendi: {ad}  md5 {md5(os.path.join(veri, ad))}")
    dll = os.path.join(veri, "Managed", "Assembly-CSharp.dll")
    yedek_dll = os.path.join(yedek, "Managed", "Assembly-CSharp.dll")
    if os.path.isfile(yedek_dll):
        atomik_yaz(yedek_dll, dll)
        print(f"  geri yuklendi: Managed/Assembly-CSharp.dll")
    elif os.path.isfile(dll):
        arac = arac_yolu()
        if arac and os.name != "nt" and not os.access(arac, os.X_OK):
            try:
                os.chmod(arac, 0o755)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions -- calistirilabilir arac icin gerekli
            except OSError:
                pass
        if arac:
            cikti = dll + ".tr-temiz"
            r = subprocess.run([arac, "--kaldir", dll, cikti], capture_output=True, text=True)
            if r.returncode == 0 and os.path.isfile(cikti):
                atomik_yaz(cikti, dll)
                os.remove(cikti)
                print("  TR dil kodu DLL'den kaldirildi")

    print("\nOrijinal dosyalar geri yuklendi.")
    print("NOT: Dil ayariniz TR kayitliysa, oyunu acmadan once ayarlardan EN secin")
    print("     veya dil ayarini sifirlayin; aksi halde secili dil bulunamaz.")


def main():
    ap = argparse.ArgumentParser(description="Hollow Knight TR dil paketi patcher")
    ap.add_argument("oyun", nargs="?", help="oyun klasoru veya hollow_knight_Data")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--geri-al", action="store_true")
    ap.add_argument("--zorla", action="store_true",
                    help="desteklenmeyen Unity surumunde de dene (risk size aittir)")
    a = ap.parse_args()

    if a.oyun:
        veri = veri_dizini(a.oyun)
    else:
        bulunan = oyun_ara()
        if not bulunan:
            raise SystemExit("HATA: Hollow Knight klasoru bulunamadi.\n"
                             "     Oyun klasorunu bu dosyanin uzerine surukleyip birakin.")
        veri = veri_dizini(bulunan)
    print(f"Veri dizini: {veri}\n")
    if a.geri_al:
        geri_al(veri)
    else:
        if tr_uygula(veri, a.dry_run, a.zorla) is False:
            return 2   # TR metinleri yazildi ama dil listesi yamalanamadi
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
