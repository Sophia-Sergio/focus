rename survey_id folio
label variable folio "folio. Folio"

rename q# p#, renumber

rename student_gender sexo
label variable sexo "sexo. Género estudiante"

rename type trt_ctrl
label variable trt_ctrl "trt_ctrl. Tratamiento o Control"
drop grade_range

rename Nombrefinal nombre
label variable nombre "nombre. Nombre estudiante"

rename subtype tipo
label variable tipo "tipo. Tipo encuesta (A o B)"

replace tipo = "a" if tipo == "TEST-A"
replace tipo = "b" if tipo == "TEST-B"

rename date fecha
label variable fecha "fecha. Fecha toma de encuesta"


label variable letra "letra. Letra curso"

label variable curso "curso. Curso estudiante"
label variable region "region. Region Establecimiento"
label variable nom_est "nom_est. Nombre Establecimiento"
label variable rbd "rbd. RBD Establecimiento"


