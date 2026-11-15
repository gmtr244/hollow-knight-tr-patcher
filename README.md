# Hollow Knight - Türkçe Dil Paketi (Patcher)

Bu paket oyuna ayrı bir "TR" (Türkçe) dil seçeneği ekler.
İngilizce, Korece ve diğer diller olduğu gibi kalır.

ÖNEMLİ: Bu paket oyun dosyası İÇERMEZ. Kendi Hollow Knight
kopyanızı yamalar. Çeviri metinleri pakete dahildir.

Gereken: Hollow Knight 1.5.12620 (Steam, Unity 6000.0.61f1) —
Windows veya Linux (Steam / Proton). Betik oyunun Unity sürümünü
kontrol eder; farklı bir sürümde hiçbir şeyi değiştirmeden durur.
(Yine de denemek isterseniz betiğe --zorla ekleyin; risk size aittir.)

--------------------------------------------------------------------
WINDOWS
--------------------------------------------------------------------
1. Oyunu tamamen kapatın.
2. KUR.bat dosyasına çift tıklayın.
   Oyunu bulamazsa KUR.bat üzerine oyun klasörünü sürükleyip bırakın.
3. Bitince oyunu açın:
   SEÇENEKLER (Options) → dil satırı → listede en sonda "TR".

Geri almak için: KALDIR.bat

Not: Python veya başka bir şey kurmanız GEREKMEZ; her şey paketin
içinde.

--------------------------------------------------------------------
LINUX
--------------------------------------------------------------------
1. Oyunu kapatın.
2. Terminalde bu klasöre girin:
     bash KUR.sh
   (Oyunu bulamazsa: bash KUR.sh "/yol/Hollow Knight")
3. İlk çalıştırmada gerekli Python paketi (UnityPy) otomatik
   kurulur; internet gerekir (yaklaşık 1 dakika, tek seferlik).

Geri almak için: bash KALDIR.sh

--------------------------------------------------------------------
NE YAPIYOR?
--------------------------------------------------------------------
1. resources.assets içine 36 Türkçe metin tablosu (TR_*) ekler.
2. globalgamemanagers içindeki kaynak indeksine bu tabloları yazar.
3. Türkçe karakterler (ğ ş ı İ) için yazı tipi yedeği ekler.
4. Assembly-CSharp.dll içindeki dil listesine "TR" kodunu ekler.

Yapmadan önce:
- Oyunun açık olup olmadığını ve Unity sürümünü kontrol eder.
- Dosya yapısını (dil tabloları, kaynak indeksi, font, dil listesi)
  doğrular; tanımadığı bir yapıda hiçbir şeyi değiştirmez.
- Değişiklikleri geçici dosyaya yazıp tekrar açarak doğrular;
  ancak doğrulama geçerse yerine koyar.
- Orijinalleri hollow_knight_Data/.tr-dil-paketi-yedek/ altına alır.
  Oyun sonradan güncellenmişse (dosyalar değişmişse) yedeği yeniler;
  böylece KALDIR eski sürümün dosyalarını yeni sürümün üstüne yazmaz.
  Yazma sırasında bir hata olursa, o ana kadar yazılan dosyaları yedekten geri alır;
  oyun yarım yamalı kalmaz.

--------------------------------------------------------------------
NOTLAR
--------------------------------------------------------------------
* Steam'de "Oyun dosyalarının bütünlüğünü doğrula" derseniz dosyalar
  orijinaline döner, TR seçeneği kaybolur. KUR'u tekrar çalıştırın.

* Kaldırdıktan sonra oyun dil ayarınız TR kayıtlıysa oyun açılmadan
  önce ayarlardan EN seçin (ya da dil ayarını sıfırlayın).

* Steam Cloud / kayıt dosyalarınıza dokunulmaz.

* Bu paket tekrar tekrar çalıştırılabilir; ikinci kez hiçbir şeyi
  yeniden eklemez (idempotent).

--------------------------------------------------------------------
DOSYALAR
--------------------------------------------------------------------
KUR.bat / KUR.sh ............ kurulum
KALDIR.bat / KALDIR.sh ...... kaldırma
patcher/hk-tr-patch.py ...... yamalama betiği
patcher/tr-veri/ ............ Türkçe metinler (şifreli bloklar)
enumpatch/enumpatch[.exe] ... dil listesi aracı (Mono.Cecil)
python/ ..................... Windows için gömülü Python (Windows sürümü)

Çeviri topluluk çevirisidir; Hollow Knight ve dosya biçimleri
Team Cherry'ye aittir.

## Depo yapısı

```
windows/   Windows paketi: KUR.bat, KALDIR.bat, patcher/ (yama + çeviri verisi)
linux/     Linux paketi:   KUR.sh,  KALDIR.sh,  patcher/ (yama + çeviri verisi)
enumpatch/ Dil listesine TR ekleyen C# aracının kaynağı (Mono.Cecil)
tools/     Yardımcı betikler
```

`enumpatch.exe`, `enumpatch` ve gömülü Python ikili dosyaları depoya konmaz;
**Releases** sayfasındaki hazır zip'lerde bulunur. Normal kullanıcılar
Releases'ten kendi işletim sistemine uygun zip'i indirmelidir.

## Kaynaktan derleme (enumpatch)

```
cd enumpatch
dotnet publish -c Release -r linux-x64 --self-contained true \
    -p:PublishSingleFile=true -p:PublishTrimmed=true -p:InvariantGlobalization=true -o pub-linux
dotnet publish -c Release -r win-x64 --self-contained true \
    -p:PublishSingleFile=true -p:PublishTrimmed=true -p:InvariantGlobalization=true -o pub-win
```

## Dosya bütünlüğünü doğrulama

Her release için `SHA256SUMS` yayınlanır. İndirdiğiniz zip'i kontrol edin:

```
sha256sum -c SHA256SUMS --ignore-missing
```

## Lisans

Kod: GNU GPL v3 (yalnızca v3, `GPL-3.0-only`; bkz. `LICENSE`, `THIRD_PARTY.md`). Hollow Knight ve oyun içeriği
Team Cherry'ye aittir; bu depo oyun dosyası içermez.
