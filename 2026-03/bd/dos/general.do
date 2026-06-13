capture program drop folio_dups
program define folio_dups
	duplicates tag folio, gen(dup_flag)
	edit if dup_flag > 0
end

cd "/Users/sergiotorres/code/personal/focus/2026-03/bd"

// 4-5
import delimited "4-5_consolidated.csv", clear

tempfile main45
save `main45'

import delimited "4_5_revisión.csv", clear
keep sheet survey_id nombres_ai check_nom check_ape nombres apellidos_ai apellidos ///
     rut_ai check_rut rut_rev edad_ai check_edad edad_rev started
rename survey_id folio
tempfile rev45
save `rev45'

use `main45', clear
run "dos/label_general"
run "dos/replace_general"

merge 1:1 folio using `rev45', keep(master match) nogenerate

replace nombres = nombres_ai if check_nom == 1
replace apellidos = apellidos_ai if check_ape == 1

replace rut = rut_rev if check_rut == 2
replace rut = rut_ai if check_rut == 1

replace edad = edad_rev if check_edad == 2
replace edad = edad_ai if check_edad == 1

drop *_ai check* *_rev started
order folio region nom_est rbd curso letra tipo nombres apellidos
label variable nombres "nombres. Nombres estudiante"
label variable apellidos "apellidos. Apellidos estudiante"


sort folio
run "dos/4_5_survey_replaces"

drop if p1 == . & p2 == . & p3 == . & p46 ==. & p8 == . & p41 == . & p32 == . & p7 == . & p22 == .
drop sheet

run "dos/validacion_rut"

preserve
    keep if tipo == "a"
	run "dos/4_5_label_general_A.do"
	log using "entrega/4_5_A_codebook.log", replace text
	describe
	codebook
	log close
    save "entrega/bd_4_5_tipo_A.dta", replace
restore

preserve
    keep if tipo == "b"
	run "dos/4_5_label_general_B.do"
	log using "entrega/4_5_B_codebook.log", replace
		codebook
	log close
    save "entrega/bd_4_5_tipo_B.dta", replace
restore

run "dos/4_5_label_general_A.do"
run "dos/4_5_reorder.do"

save "entrega/bd_4_5_consolidada.dta", replace

use "entrega/bd_4_5_consolidada.dta"
log using "entrega/4_5_codebook.log", replace
codebook
log close

use  "entrega/bd_4_5_tipo_A.dta"
log using "entrega/4_5_A_codebook.log", replace text
codebook
log close

use  "entrega/bd_4_5_tipo_B.dta"
log using "entrega/4_5_B_codebook.log", replace text
codebook
log close


// gen folio_ab = regexm(upper(folio), "A") | regexm(upper(folio), "B")
// edit folio rbd curso letra rut nom_est if folio_ab == 1
// edit rbd curso letra

// 6-7
import delimited "6-7_consolidated.csv", clear

tempfile main67
save `main67'

import delimited "6_7_revisión.csv", clear
keep sheet survey_id nombres_ai check_nom check_ape nombres apellidos_ai apellidos ///
     rut_ai check_rut rut_rev edad_ai check_edad edad_rev started
rename survey_id folio
tempfile rev67
drop if  folio == "Lista de Curso 6A"  || folio == "Lista de Curso 6B" || folio == "Lista de Curso 7A" || folio == "Lista de Curso 7B"
save `rev67'

use `main67', clear
run "dos/label_general"
run "dos/replace_general"

merge 1:1 folio using `rev67', keep(master match) nogenerate

replace nombres = nombres_ai if check_nom == 1
replace apellidos = apellidos_ai if check_ape == 1

replace rut = rut_rev if check_rut == 2
replace rut = rut_ai if check_rut == 1

replace edad = edad_rev if check_edad == 2
replace edad = edad_ai if check_edad == 1

drop *_ai check* *_rev started
order folio region nom_est rbd curso letra tipo nombres apellidos
label variable nombres "nombres. Nombres estudiante"
label variable apellidos "apellidos. Apellidos estudiante"

sort folio
run "dos/6_7_survey_replaces.do"

drop if p1 == . & p2 == . & p60 == . & p17 == . & p23 == . & p28 == . & p38 == . & p48 == . & p37 == .
drop if folio == "Lista de Curso 7A" || folio == "Lista de Curso 6A"
drop sheet

run "dos/validacion_rut"

preserve
    keep if tipo == "a"
	run "dos/6_7_label_general_A.do"
	log using "entrega/6_7_A_codebook.log", replace
		codebook
	log close
    save "entrega/bd_6_7_tipo_A.dta", replace
restore

preserve
    keep if tipo == "b"
	run "dos/6_7_label_general_B.do"
	log using "entrega/6_7_B_codebook.log", replace
		codebook
	log close
    save "entrega/bd_6_7_tipo_B.dta", replace
restore

run "dos/6_7_label_general_A.do"
run "dos/6_7_reorder.do"
log using "entrega/6_7_codebook.log", replace
	codebook
log close

save "entrega/bd_6_7_consolidada.dta", replace


use "entrega/bd_6_7_consolidada.dta"
log using "entrega/6_7_codebook.log", replace
codebook
log close

use  "entrega/bd_6_7_tipo_A.dta"
log using "entrega/6_7_A_codebook.log", replace text
codebook
log close

use  "entrega/bd_6_7_tipo_B.dta"
log using "entrega/6_7_B_codebook.log", replace text
codebook
log close





// gen folio_ab = regexm(upper(folio), "A") | regexm(upper(folio), "B")
// edit folio rbd curso letra rut nom_est if folio_ab == 1
sort rbd curso letra folio
edit rbd curso letra
edit if p1 == . & p2 == . & p15 == . & p27 == . & p8 == . & p40 == .
