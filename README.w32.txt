Efterfølgende vejledning er delt op i 7 dele. Ikke alle dele er nødvendige for at få et XMLTV baseret system 
op at stå:

Punkt 1 er nødvendig hvis du vil køre med grabberne som er beskrevet under punkt 2 eller 3. 

Punkt 2 er nødvendig hvis du vil køre med grabberen som henter fra tv2.dk. Den grabber henter afsnitsnumre til 
relativt mange udsendelser, men mangler sluttidspunkt for sidste udsendelse hver dag og har ikke afsnitsnavne 
for særlig mange udsendelser. 

Punkt 3 er nødvendig hvis du vil køre med grabberen som henter fra tdckabeltv.dk. Den grabber er god til at hente 
kategorier, afsnitsnavne og titler på originalsprog, men mangler afsnitsnumre. 

Punkt 4 er nødvendig hvis du vil køre med grabberne som henter fra tv-guiden.dk, ahot.dk, jubii.dk eller ontv.dk 
eller hvis du vil kombinere flere grabbere (se punkt 6).

Punkt 5 kan bruges hvis du vil køre med grabberne som henter fra tv-guiden.dk, ahot.dk, jubii.dk eller ontv.dk. 
Hvad de enkelte grabbere er specielt gode eller dårlige til kan du se i filen grabbersammenligning.pdf, hvor 
grabberne er kørt som test og skemaet viser hvor mange procent af udsendelserne, som havde de angivne 
informationer (tags). Det er lidt indforstået: F.eks betyder tagget "sub-titleda" dansksproget afsnitsnavn. 

Punkt 6 kan bruges hvis du vil kombinere flere grabbere. 
Alternativt til punkt 6 kan man læse i ReadMe_tv_grab_dk_all.txt om hvordan man bruger filegrabber.py til 
automatisk at downloade grabberne som er nævnt under punkt 5 og køre dem alle sammen med tdc og tv2 grabberne 
og kombinere outputtet.

Punkt 7 siger stort set bare at du skal kigge i dokumentationen til dit mediasoftware for at finde ud af 
hvordan du får den resulterende XMLTV fil ind og dette er selvfølgelig nødvendigt.

Så forskellige fremgangsmåder kunne være: 

Punkt 1+2+7 så kører du på tv2.dk 
Punkt 1+3+7 så kører du på tdckabeltv.dk 
Punkt 4+5+7 så kører du f.eks på ontv.dk 
Punkt 1+2+3+4+ReadMe_tv_grab_dk_all.txt+7, så kører du på en kombination af tdckabeltv.dk, tv2.dk, jubii.dk, 
ahot.dk, ontv.dk og tv-guiden.dk. Det giver f.eks de længste beskrivelser til hvert program, både afsnitsnumre 
og afsnitsnavne etc. 

Kig i grabbersammenligning.pdf og find ud af hvilken grabber du helst vil starte med. Ontv.dk kan være et godt valg. 
Tdckabeltv.dk er bedre hvis du hellere vil have originaltitler end danske titler på film. Start så med en simpel 
løsning (1+3+7 eller 4+5+7) til det valg. Når du har fået det op at stå og gerne vil have bedre/mere information i 
din EPG, så prøv den store løsning (1+2+3+4+ReadMe_tv_grab_dk_all.txt+7).


1	ActivePerl til Windows
------------------------------

Grabberne til tv2.dk og tdckabeltv.dk er skrevet i Perl. Så for disse skal du have Perl installeret på dit system.
Jeg foreslår den gratis udgave af ActivePerl:
http://www.activestate.com/Products/Download/Download.plex?id=ActivePerl
Når ActivePerl er installeret, skal der installeres nogle ekstra moduler.
Download XMLTV-modules.zip fra http://uk.groups.yahoo.com/group/xmltvdk/files/ og kopier indholdet af zip-filen ind i 
Perl mappen. F.eks. C:\Perl\
Endelig skal filen Manip.pm under C:\Perl\site\lib\Date\ redigeres som følgende:

# Local timezone
$Cnf{"TZ"}="";

skal ændres til:

# Local timezone
$Cnf{"TZ"}="CET";


2	tv_grab_dk
------------------

tv_grab_dk henter dataene fra tv2's internetside.
For at bruge den skal den først konfigureres:

C:\Perl\site\lib\xmltv\dk>Perl tv_grab_dk --configure

(Bemærk at C:\Perl\bin skal registreres under Windows PATH variabel. Perl-installationen sørger automatisk for dette.)
Følg anvisningerne. Programmet vil spørge efter dit tv2-login og password. Det er ikke nødvendigt og kræver flere moduler 
end dem fra XMLTV-modules.zip
Nu er du klar til at hente dataene:

C:\Perl\site\lib\xmltv\dk>Perl tv_grab_dk --output tv2.xml --days 7


3	tv_grab_dk_tdckabeltv
-----------------------------

Denne variant henter data fra tdckabeltv's internetside. Den fungerer på samme måde som tv_grab_dk.
Hent grabberen fra filsektionen: http://uk.groups.yahoo.com/group/xmltvdk/files/
og gem den under C:\Perl\site\lib\xmltv\dk\
konfigurer og hent data:

C:\Perl\site\lib\xmltv\dk>Perl tv_grab_dk_tdckabeltv --configure

C:\Perl\site\lib\xmltv\dk>Perl tv_grab_dk_tdckabeltv --output tdc.xml --days 7


4	Python
--------------
Endelig er der en del grabbere, der er skrevet i Python. Hent den her: 
http://www.python.org/ftp/python/2.4.2/python-2.4.2.msi
og installer den. Her skal du selv definere installationsmappen (som regel C:\Python24) som en PATH for Windows XP.
For at gøre dette skal du højreklikke på Denne Computer og vælge Egenskaber. Vælg fanen Advanceret og tryk på 
Miljøvariabler.
Marker variabel Path og tryk Rediger. Her tilføjer du (uden at slette noget!): C:\Python24 og trykker Ok til det hele.


5	tv_grab_dk_tvguiden.py, tv_grab_dk_ahot.py, tv_grab_dk_jubii.py
-----------------------------------------------------------------------
Download de grabbere du vil bruge fra filsektionen og konfigurer/kør dem som følgende:

C:\Perl\site\lib\xmltv\dk>Python tv_grab_dk_tvguiden.py --configure

C:\Perl\site\lib\xmltv\dk>Python tv_grab_dk_tvguiden.py > tvguiden.xml

...


6	Merge data
------------------
Med alle disse forskellige grabbere at vælge imellem, kan det være svært at beslutte hvilken en man skal bruge.
Som hjælp kan du bruge oversigten grabbere.pdf fra filsektionen.
Men en anden mulighed er at bruge alle grabberne, for derefter at merge alle dataene sammen.
For at gøre dette skal man først sørge for at alle kanal-id'erne i xml-filerne er ens. Heldigvis er der også et 
script til dette.
Download channelid.py og channelidparsefiler.zip fra filsektionen og gem dem samme sted som dine xml-filer (udpak 
filerne fra zip-filen).
Kør nu channelid-scriptet på alle xml-filerne:

C:\Perl\site\lib\xmltv\dk>Python channelid.py --iso tv2parsefile tv2.xml tv2_id.xml

...

Nu kan dataene merges med scriptet xmltvmerger.py (fra filsektionen):

C:\Perl\site\lib\xmltv\dk>Python xmltvmerger.py jubii_id.xml ahot_id.xml epg_merge1.xml

C:\Perl\site\lib\xmltv\dk>Python xmltvmerger.py epg_merge1.xml tv2_id.xml epg_merge2.xml

C:\Perl\site\lib\xmltv\dk>Python xmltvmerger.py epg_merge2.xml tvguiden_id.xml epg_merge3.xml

C:\Perl\site\lib\xmltv\dk>Python xmltvmerger.py epg_merge3.xml tdc_id.xml epg_merged.xml

Alternativt kig i ReadMe_tv_grab_dk_all.txt som fortæller hvordan man gør alt dette automatisk ved hjælp af
scriptet filegrabber.py


7	Importer dataene ind i EPG'en (EPG=Electronic Program Guide)
--------------------------------------------------------------------
Når du har været igennem det hele, så skulle du gerne ende med det bedste fra alle grabberne i epg_merged.xml
Nu mangles der bare at importere det ind i din tv-software.
Hvordan dette gøres varieres fra program til program, så det må du selv finde ud af.
Bemærk! Det er muligt at tv-softwaren kræver en xmltv.dtd fil. Denne kan skaffes fra den komplette xmltv-version:
http://sourceforge.net/project/showfiles.php?group_id=39046 - nyeste version til W32 i øjeblikket findes under 
xmltv-0.5.42a-win32.zip

Endelig kan du lave en batch-fil med alle kommandoerne og få den til at opdatere din EPG hver dag ved hjælp af 
Windows XP's Scheduler.
Husk: Du behøver kun at konfigurere grabberne een gang - medmindre du vil ændre kanalerne.
Perl-grabberne gemmer en konfigurationsfil under .\.xmltv - gerne C:\Perl\site\lib\xmltv\dk\.xmltv
mens Python-grabberne gemmer dem under ~\.xmltv - gerne: C:\Documents and Settings\"Dit brugernavn"\.xmltv

Filen bladerunnerpro.rar i gruppens filsektion indeholder filer og vejledning (se readme.txt i arkivet).
Hvis du har problemer med at pakke filarkivet ud, så brug evt http://7-zip.org.

# $Id$
