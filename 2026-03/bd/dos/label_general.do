drop if survey_id == "45314B15"
replace survey_id = "10734" + substr(survey_id, 6, .) if school_name == "CENTRO EDUC. PART. MARIA REINA INMACULADA"

rename survey_id folio
label variable folio "folio. Folio"

rename q# p#, renumber

rename student_gender sexo
label variable sexo "sexo. Sexo estudiante"

tostring school_folder, replace force


replace grade_folder = school_folder if grade_range == "4° - 5°" & inlist(folio, "45314B1", "45314B11", "45314B12", "45314B13", "45314B14", "45314B15", "45314B16", "45314B17")
replace grade_folder = school_folder if grade_range == "4° - 5°" & inlist(folio, "45314B2", "45314B3", "45314B4", "45314B5", "45314B6", "45314B7", "45314B8", "45314B9", "45314B10")

gen curso = substr(grade_folder, 1, length(grade_folder) - 1)
gen letra = substr(grade_folder, -1, 1)

drop if folio == "Lista de Curso 4A" || folio == "Lista de Curso 4B" || folio == "Lista de Curso 5A" || folio == "Lista de Curso 5B" || folio == "Lista Curso 4B"
drop if folio == "45314A1" && type == "TEST" 


rename type tipo
label variable tipo "tipo. Tipo encuesta (A o B)"

gen rbd = regexs(1) if regexm(folio, "^([0-9]+)[0-9][A-Za-z]")
destring rbd, replace force
destring curso, replace force


drop grade_folder


replace tipo = "a" if folio == "47375B4" || folio == "48075A4"
replace tipo = "a" if tipo == "TEST-A" || tipo == "A"
replace tipo = "b" if tipo == "TEST-B"  || tipo == "B"
replace tipo = "b" if tipo == "EST-B"

drop if tipo == "Lista" ||  tipo == "Lista de Curso" ||  tipo == "SÉPTIMO" || tipo == "Lista de Curso 7A" || folio == "Lista de Curso 6A"  || folio == "Lista de Curso 6B" || folio == "Lista de Curso 7A"
drop if folio == "Lista de Curso 7B"

rename date fecha
label variable fecha "fecha. Fecha toma de encuesta"


label variable letra "letra. Letra curso"

label variable curso "curso. Curso estudiante"

rename student_run rut
label variable rut "rut. Rut curso"

rename student_age edad
label variable edad "edad. Rut curso"

label variable rbd "rbd. RBD Establecimiento"

rename school_folder nom_est
label variable nom_est "nom_est. Nombre Establecimiento"


gen region = .

label variable region "region. Region Establecimiento"

label define nivel_acuerdo 1 "No es cierto", modify
label define nivel_acuerdo 2 "Poco cierto", modify
label define nivel_acuerdo 3 "Bastante Cierto", modify
label define nivel_acuerdo 4 "Muy cierto", modify

label define freq 1 "Nunca", modify
label define freq 2 "Rara vez", modify
label define freq 3 "A veces", modify
label define freq 4 "Siempre", modify

label define sexo 1 "Hombre", modify
label define sexo 2 "Mujer", modify
label define sexo 3 "Prefiero no decir", modify
label values sexo sexo

