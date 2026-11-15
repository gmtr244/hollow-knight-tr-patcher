// SPDX-License-Identifier: GPL-3.0-only
using Mono.Cecil;

// GlobalEnums.SupportedLanguages enum'ina dil kodu ekler / kaldirir.
//   enumpatch <giris.dll> <cikis.dll> [KOD]     -> ekle (yoksa)
//   enumpatch --kaldir <giris.dll> <cikis.dll> [KOD]
//   enumpatch --check <dll> [KOD]

if (args.Length < 2)
{
    Console.WriteLine("kullanim: enumpatch <giris.dll> <cikis.dll> [KOD]");
    Console.WriteLine("         enumpatch --kaldir <giris.dll> <cikis.dll> [KOD]");
    Console.WriteLine("         enumpatch --check <dll> [KOD]");
    return 1;
}

bool kontrol = args[0] == "--check";
bool kaldir = args[0] == "--kaldir";
string giris = kontrol ? args[1] : (kaldir ? args[1] : args[0]);
string cikis = kontrol ? "" : (kaldir ? args[2] : args[1]);
string kod = "TR";
string son = args[^1];
if (son.Length is >= 2 and <= 5 && son.All(char.IsLetterOrDigit))
    kod = son.ToUpperInvariant();

var cozucu = new DefaultAssemblyResolver();
var kok = Path.GetDirectoryName(Path.GetFullPath(giris))!;
cozucu.AddSearchDirectory(kok);

if (kontrol)
{
    var c = AssemblyDefinition.ReadAssembly(giris, new ReaderParameters { AssemblyResolver = cozucu });
    var t = c.MainModule.GetType("GlobalEnums.SupportedLanguages");
    if (t == null || !t.IsEnum) { Console.WriteLine("HATA: enum bulunamadi"); return 2; }
    var f = t.Fields.FirstOrDefault(x => x.Name == kod);
    Console.WriteLine(f == null ? $"{kod} yok" : $"{kod} = {f.Constant}");
    return f == null ? 3 : 0;
}

var asm = AssemblyDefinition.ReadAssembly(giris,
    new ReaderParameters { ReadWrite = false, AssemblyResolver = cozucu });
var tip = asm.MainModule.GetType("GlobalEnums.SupportedLanguages");
if (tip == null || !tip.IsEnum)
{
    Console.WriteLine("HATA: GlobalEnums.SupportedLanguages bulunamadi");
    return 2;
}

var var_olan = tip.Fields.FirstOrDefault(f => f.Name == kod);

if (kaldir)
{
    if (var_olan == null)
    {
        Console.WriteLine($"{kod} zaten yok; degisiklik gerekmedi");
        return 0;
    }
    tip.Fields.Remove(var_olan);
    Console.WriteLine($"{kod} kaldirildi");
}
else if (var_olan != null)
{
    Console.WriteLine($"{kod} zaten var (deger {var_olan.Constant}); degisiklik gerekmedi");
    return 0;
}
else
{
    int en_buyuk = tip.Fields.Where(f => f.Name != "value__" && f.Constant != null)
        .Select(f => Convert.ToInt32(f.Constant)).Max();
    var sablon = tip.Fields.First(f => f.Name == "EN");
    var yeni = new FieldDefinition(kod,
        FieldAttributes.Public | FieldAttributes.Static | FieldAttributes.Literal | FieldAttributes.HasDefault,
        sablon.FieldType);
    yeni.Constant = en_buyuk + 1;
    tip.Fields.Add(yeni);
    Console.WriteLine($"{kod} = {en_buyuk + 1} eklendi");
}

asm.Write(cikis);
Console.WriteLine("yazildi: " + cikis);
return 0;
