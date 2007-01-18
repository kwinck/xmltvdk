Hvordan man nemt henter data fra seks-syv forskellige kilder i xmltv.

1) Hav python og perl installeret.

2) Installer tv2grabberen f.eks. fra XMLTV-modules.zip. Se hvordan det gøres på windows i "README.w32.txt". På fedora kan det gøres med "yum install xmltv" fra atrpms.

3) Download filegrabber.py fra gruppens filer

4) Kør "python filegrabber.py" *

5) Hvis du ikke kører *nix system eller ikke har tv2 grabberen liggende i
/usr/bin/tv_grab_dk skal du rette tv_grab_dk_all.py med den rigtige placering.
(Omkring linje 20)

6) Kør "python xmltv/tv_grab_dk_all.py --configure" **

7) Kør "python xmltv/tv_grab_dk_tdc.py" for at konfigurere tdc grabberen. Dens konfigurationsfil har et format 
som gør at tv_grab_dk_all ikke kan konfigurere den direkte.

8) Kør "python xmltv/tv_grab_dk_all.py --out ud.xml" ***

Nu burde ud.xml være en fuld merged, timefixet etc. xmltvfil lige til at
fodre sine programmer med. Når man senere kører grabberen igen, sørger
den automatisk for at hente nyeste grabber/parser/util-filer fra
gruppen, så alt er up to date****.

Grabberen er fuld stabil for mig, men sig endelig til, hvis den f.eks.
fejler på et windowssystem.
Outputtet er også meget rodet. Det burde dog ikke være vanskeligt at
rette i en senere version.

Det er muligt at slå grabbere fra, sætte flere grabbere til eller ændre merge-rækkefølgen via linie 7 i 
tv_grab_dk_all.py:

   mergeorder = ("jubii","tv2","tdc","ahot","tvguiden","ontv")

Fjern de grabbere, som du ikke vil have startet eller skift rækkefølgen. F.eks har "tdc" mange titler på originalsprog,
men hvis "tdc" ikke er den første i merge rækkefølgen, så bliver originalsprogstitlerne oftest skjult af den danske titel.
"tvguiden" har meget gode og lange beskrivelse til programmerne, men bytter ofte rundt i hvilke programmer der 
sendes hvornår. Så den er ofte årsag til at programmer har forkert beskrivelse. Hvis dette er et problem for
dig, så kan du slå "tvguiden" fra.

Du kan også tilføje den svenske grabber tv_grab_se_swedb, da den har de fleste programmer som sendes via det 
svenske DVB-T net. Jeg mener at den grabberen følger med xmltv pakken, så den burde ligge samme sted som tv2 
grabberen (tv_grab_dk). tv_grab_dk_all.py er forberedt til den svenske grabber, så du skal bare tilføje "swedb" 
i mergeorder tabellen.

--

Noter:

* Denne komando vil lave en mappe kaldet "xmltv" med alle nødvendige
filer. Hvis du hellere vil have mappen et andet sted, eller med et andet
navn, så ret det i sidste linje i filegrabber.py.
Du vil også bliver spurgt om dit yahoo brugernavn og password, der
bruges til at hente filerne.

** Hvis man i starten har brug for at kalde tv_grab_dk_all.py ofte, kan
man med fordel bruge "--noupdate" kommandoen, så tingene kører lidt
hurtigere.

*** Hvis tv_grab_dk_all.py kaldes uden et "--out" argument, bliver filen
gemt i samme mappe som tv_grab_dk_all.py (her xmltv) ved et navn ala
jubiitv2tdcahottvguidenontv_time.

**** Bemærk at tv_grab_dk_all.py ikke automatisk opdaterer sig selv og
filegrabber.py. Skal disse filer opdateres, må du enten selv køre
filegrabber.py eller hente filerne i gruppen.
