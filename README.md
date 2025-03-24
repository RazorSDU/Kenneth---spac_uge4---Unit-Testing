# PDF downloader
Simpelt script til at downloade pdf filer, hvis url addresser hentes fra en Excel fil.

## Før brug
Kør `pip install -r requirements.txt`, evt. i et virtual environment.

## Kørsel
Brug kommandoen `py dlpdf.py "excel-fil" "output-folder"`, hvor
* `excel-fil` er stien til excel filen der skal trækkes links ud af.
* `output-folder` er mappen hvor pdf-filerne gemmes, fx. `./downloads`

Hvis ingen argumenter er angivet, benyttes der standard argumenter, som står i .py filen.