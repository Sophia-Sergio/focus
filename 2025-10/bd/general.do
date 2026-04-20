program drop folio_dups
program define folio_dups
	duplicates tag survey_id, gen(dup_flag)
	edit if dup_flag == 1
end


capture log close

cd "/Users/sergiotorres/code/focus/"

// muestra

import excel "/Users/sergiotorres/code/focus/bd/muestra.xlsx", sheet("Hoja1") firstrow clear
tostring folio, replace
rename folio survey_id
keep if curso == 4 | curso == 5
save "muestra_4_5.dta", replace

import excel "/Users/sergiotorres/code/focus/bd/muestra.xlsx", sheet("Hoja1") firstrow clear
tostring folio, replace
rename folio survey_id
keep if curso == 6 | curso == 7
save "muestra_6_7.dta", replace


// 4-5
import delimited "digitalizadas/4-5_consolidated_2d_attemp.csv", clear
merge 1:1 survey_id using "muestra_4_5.dta"
keep if _merge == 3 | _merge ==1
run "bd/label_general"
run "bd/replace_general"
run "bd/4_5_nom_rut_con"

// replace todo = "revisar encuesta física" if folio == "47624D6"
// replace todo = "revisar encuesta física, tiene las páginas erroneas" if folio == "561020"
replace todo = "revisar, se hizo en encuesta de 6-7" if folio == "104055B8"
replace todo = "revisar, se hizo en encuesta de 6-7" if folio == "21554A4"
replace tipo = "TEST-B" if tipo == "TEST-BCLSD"

replace curso = 5 if folio == "104055B10"
replace curso = 5 if folio == "108515A3"
replace curso = 4 if folio == "43074A9"
replace curso = 5 if folio == "47625E3"
edit if curso == .
tab letra, miss

gen obs = ""
replace obs = "responde al azar" if folio == "400384B1"
replace letra = "B" if folio == "311087"
replace curso = 4 if folio == "312535A2"
replace folio = "312534A6" if folio == "312535A2"
replace tipo = "b" if folio == "581015"
sort rbd curso letra folio

run "bd/validacion_rut"


preserve
    keep if tipo == "a"
	run "bd/4_5_label_general_A.do"
	drop obs
	log using "bd/entrega/4_5_A_codebook.log", replace text
	describe
	codebook
	log close
    save "bd/entrega/bd_4_5_tipo_A.dta", replace
restore

preserve
	drop obs
    keep if tipo == "b"
	run "bd/4_5_label_general_B.do"
	log using "bd/entrega/4_5_B_codebook.log", replace
		codebook
	log close
    save "bd/entrega/bd_4_5_tipo_B.dta", replace
restore

run "bd/4_5_label_general_A.do"
run "bd/4_5_reorder.do"
drop obs

save "bd/entrega/bd_4_5_consolidada.dta", replace


use "bd/entrega/bd_4_5_consolidada.dta"
log using "bd/entrega/4_5_codebook.log", replace
codebook
log close

use  "bd/entrega/bd_4_5_tipo_A.dta"
log using "bd/entrega/4_5_A_codebook.log", replace text
codebook
log close

use  "bd/entrega/bd_4_5_tipo_B.dta"
log using "bd/entrega/4_5_B_codebook.log", replace text
codebook
log close




// gen folio_ab = regexm(upper(folio), "A") | regexm(upper(folio), "B")
// edit folio rbd curso letra rut nom_est if folio_ab == 1
// edit rbd curso letra

// 6-7
import delimited "digitalizadas/6-7_consolidated_2d_attemp.csv", clear
merge 1:1 survey_id using "muestra_6_7.dta"
keep if _merge == 3 | _merge ==1
run "bd/label_general"
run "bd/replace_general"
run "bd/6_7_nom_rut_con"

replace letra = "B" if folio == "552167"
sort rbd curso letra folio

run "bd/validacion_rut"

preserve
    keep if tipo == "a"
	run "bd/4_5_label_general_A.do"
	log using "bd/entrega/6_7_A_codebook.log", replace
		codebook
	log close
    save "bd/entrega/bd_6_7_tipo_A.dta", replace
restore

preserve
    keep if tipo == "b"
	run "bd/6_7_label_general_B.do"
	log using "bd/entrega/6_7_B_codebook.log", replace
		codebook
	log close
    save "bd/entrega/bd_6_7_tipo_B.dta", replace
restore

run "bd/6_7_label_general_A.do"
run "bd/6_7_reorder.do"
log using "bd/entrega/6_7_codebook.log", replace
	codebook
log close
drop todo
save "bd/entrega/bd_6_7_consolidada.dta", replace


use "bd/entrega/bd_6_7_consolidada.dta"
log using "bd/entrega/6_7_codebook.log", replace
codebook
log close

use  "bd/entrega/bd_6_7_tipo_A.dta"
log using "bd/entrega/6_7_A_codebook.log", replace text
codebook
log close

use  "bd/entrega/bd_6_7_tipo_B.dta"
log using "bd/entrega/6_7_B_codebook.log", replace text
codebook
log close





// gen folio_ab = regexm(upper(folio), "A") | regexm(upper(folio), "B")
// edit folio rbd curso letra rut nom_est if folio_ab == 1
sort rbd curso letra folio
edit rbd curso letra
edit if p1 == . & p2 == . & p15 == . & p27 == . & p8 == . & p40 == .
