replace rut = "" if rut == "0-0"
replace grade = "4" if grade == "4°"
replace grade = "5" if grade == "5°"
replace grade = "6" if grade == "6°"
replace grade = "6" if grade == "6°C" 
replace grade = "7" if grade == "7°"
destring grade, replace
replace curso = grade if curso == .
drop grade

replace section = "" if section == "5°"
replace section = "" if section == "4"
replace section = "" if section == "6°"
replace section = "" if section == "7"
replace section = "" if section == "0"

replace letra = section if letra == ""
replace letra = section_folder if letra != "A" & letra != "B" & letra != "C" & letra != "D" & letra != "E"
replace letra = section_folder if letra == ""
drop section
drop section_folder
drop school_folder
drop grade_folder
drop total_questions
drop completion_status
drop school_name

gen rut_final = rutfinal + "-" + dv if rutfinal != ""
replace rut_final = student_run if rut_final == ""
rename rut_final rut
label variable rut "rut. Rut estudiante"

drop student_run
drop dv
drop rutfinal

gen rbd_str = substr(folio, 1, length(folio) - 3) if rbd == .
replace rbd_str = "18181" if rbd_str == "181814"
replace rbd_str = "4762" if rbd_str == "47625"
replace rbd_str = "4973" if rbd_str == "49735"
replace rbd_str = "4307" if rbd_str == "43074"
replace rbd_str = "10405" if rbd_str == "104055"
replace rbd_str = "10407" if rbd_str == "104074"
replace rbd_str = "10401" if rbd_str == "104017"

replace rbd_str = "10403" if rbd_str == "104036"
replace rbd_str = "4762" if rbd_str == "47625"
replace rbd_str = "4973" if rbd_str == "49735"
replace rbd_str = "4307" if rbd_str == "43074"
replace rbd_str = "10405" if rbd_str == "104055"
replace rbd_str = "10835" if rbd_str == "108356"
replace rbd_str = "10836" if rbd_str == "108366"
replace rbd_str = "4868" if rbd_str == "48686"

destring rbd_str, replace
replace rbd = rbd_str if rbd == .
drop rbd_str
drop Tipo
drop _merge
drop Tipodeformulario
drop Formaquetocalineaintermedia

gen todo = ""

replace trt_ctrl = "CTR" if trt_ctrl == "CFR"
replace nombre = student_name if nombre == ""
drop student_name

replace nom_est = "Andalien de Colina" if rbd == 10404
replace nom_est = "Centro Educación Evangélico De Hualpén" if rbd == 4782
replace nom_est = "Colegio Alto del Maipo" if rbd == 31253
replace nom_est = "Colegio Colegio Martín Luther" if rbd == 4650
replace nom_est = "Colegio Inmaculada Concepcion" if rbd == 2455
replace nom_est = "Colegio Instituto San Jose" if rbd == 5153
replace nom_est = "Colegio instituto San Luis de Curacaví" if rbd == 10851
replace nom_est = "Colegio Luis Amigo" if rbd == 4868
replace nom_est = "Colegio Particular Subv. Children School" if rbd == 15515
replace nom_est = "Colegio Particular Whipple School" if rbd == 2155
replace nom_est = "Colegio San José de Cabrero" if rbd == 4307
replace nom_est = "Colegio San Manuel" if rbd == 24675
replace nom_est = "Colegio San Martín" if rbd == 2220
replace nom_est = "Colegio Santa Claudia" if rbd == 20449
replace nom_est = "Colegio Santa Luisa De Concepcion" if rbd == 4666
replace nom_est = "Colegio Whipple School Oriente" if rbd == 40038
replace nom_est = "Esc. Adriana Aranguiz Cerda" if rbd == 11248
replace nom_est = "Escuela Básica Francisco Petrinovic Karlovac" if rbd == 10409
replace nom_est = "Escuela Básica Algarrobal" if rbd == 10407
replace nom_est = "Escuela Básica f-n°372 Santa Sara" if rbd == 10427
replace nom_est = "Escuela Básica f-n° 732 Chorombo Alto" if rbd == 10836
replace nom_est = "Escuela Básica f-n° 738 Los Rulos" if rbd == 10837
replace nom_est = "Escuela Básica g-n° 733 Chorombo bajo" if rbd == 10838
replace nom_est = "Escuela Básica g-n° 734 Las Mercedes" if rbd == 10839
replace nom_est = "Escuela Básica g-n° 737 Santa Emilia" if rbd == 10840
replace nom_est = "Escuela Básica Marcos Gooycolea Cortés" if rbd == 10400
replace nom_est = "Escuela Básica Particular Paicaví de Lampa" if rbd == 26235
replace nom_est = "Escuela Básica San Vicente de lo Arcaya" if rbd == 10410
replace nom_est = "Escuela Básica Santa Marta de Liray" if rbd == 10411
replace nom_est = "Escuela Básica Santa Teresa del Carmelo" if rbd == 10401
replace nom_est = "Escuela El Saber" if rbd == 4452
replace nom_est = "Escuela Municipal Zuniga" if rbd == 2339
replace nom_est = "Escuela Particular Melecia Tocornal" if rbd == 2517
replace nom_est = "Escuela Premio Nobel Pablo Neruda" if rbd == 10403
replace nom_est = "Escuela San Francisco de Asís" if rbd == 10412
replace nom_est = "Instituto De Humanidades Antonio Moreno Casamitjana" if rbd == 17657
replace nom_est = "Instituto Humanidades Monseñor Jose Manuel Santo Ascarza" if rbd == 18181
replace nom_est = "Instituto Humanidades San Francisco De Asis" if rbd == 4973
replace nom_est = "Instituto San Sebastián Básico" if rbd == 4530
replace nom_est = "Liceo Esmeralda" if rbd == 10405
replace nom_est = "Liceo La Asuncion" if rbd == 4762
replace nom_est = "Liceo Municipal f-n° 860" if rbd == 10835

replace region = 13 if rbd == 10404
replace region = 8 if rbd == 4782
replace region = 13 if rbd == 31253
replace region = 8 if rbd == 4650
replace region = 6 if rbd == 2455
replace region = 8 if rbd == 5153
replace region = 13 if rbd == 10851
replace region = 8 if rbd == 4868
replace region = 6 if rbd == 15515
replace region = 6 if rbd == 2155
replace region = 8 if rbd == 4307
replace region = 13 if rbd == 24675
replace region = 6 if rbd == 2220
replace region = 13 if rbd == 20449
replace region = 8 if rbd == 4666
replace region = 6 if rbd == 40038
replace region = 6 if rbd == 11248
replace region = 13 if rbd == 10409
replace region = 13 if rbd == 10407
replace region = 13 if rbd == 10427
replace region = 13 if rbd == 10836
replace region = 13 if rbd == 10837
replace region = 13 if rbd == 10838
replace region = 13 if rbd == 10839
replace region = 13 if rbd == 10840
replace region = 13 if rbd == 10400
replace region = 13 if rbd == 26235
replace region = 13 if rbd == 10410
replace region = 13 if rbd == 10411
replace region = 13 if rbd == 10401
replace region = 8 if rbd == 4452
replace region = 6 if rbd == 2339
replace region = 6 if rbd == 2517
replace region = 13 if rbd == 10403
replace region = 13 if rbd == 10412
replace region = 8 if rbd == 17657
replace region = 8 if rbd == 18181
replace region = 8 if rbd == 4973
replace region = 8 if rbd == 4530
replace region = 13 if rbd == 10405
replace region = 8 if rbd == 4762
replace region = 13 if rbd == 10835

order folio trt_ctrl tipo region rbd nom_est fecha curso letra rut nombre 
sort rbd curso letra folio








