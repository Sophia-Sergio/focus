bysort rbd curso letra fecha: gen n = _N if fecha != ""
bysort rbd curso letra: egen max_n = max(n)

gen fecha_num = date(fecha, "DMY") if n == max_n
bysort rbd curso letra: egen fecha_min = min(fecha_num)
gen fecha_frecuente = string(fecha_min, "%tdDD-NN-CCYY")

drop n max_n fecha_num fecha_min
replace fecha = fecha_frecuente
drop fecha_frecuente


replace nom_est = "Escuela Municipal René Schneider Chereau" if rbd == 2115
replace nom_est = "Colegio República Argentina" if rbd == 2121
replace nom_est = "Escuela Municipal Virginia Bravo" if rbd == 2139
replace nom_est = "Instituto Regional de Educación" if rbd == 2166
replace nom_est = "Escuela Sixto Méndez Parada" if rbd == 2206
replace nom_est = "Escuela Municipal Villa la Compañía" if rbd == 2210
replace nom_est = "Escuela Municipal de San Roberto" if rbd == 2363
replace nom_est = "Escuela Olegario Lazo Baeza" if rbd == 2456
replace nom_est = "Escuela Jorge Muñoz Silva" if rbd == 2458
replace nom_est = "Escuela Bas. Fernando Arenas Almarza" if rbd == 2487
replace nom_est = "Escuela Bas. Villa Convento Viejo" if rbd == 2489
replace nom_est = "Escuela Bas. José Miguel Carrera Verdugo" if rbd == 2493
replace nom_est = "Escuela Municipal Nobeles de Chile" if rbd == 2707
replace nom_est = "Colegio Nuestra Señora del Carmen" if rbd == 4043
replace nom_est = "Escuela Guarilihue Alto" if rbd == 4052
replace nom_est = "Liceo Bicentenario de Excelencia Técnico Puente Ñuble" if rbd == 4141
replace nom_est = "Escuela Particular la Victoria" if rbd == 4275
replace nom_est = "Escuela Toqui Lautaro" if rbd == 4455
replace nom_est = "Colegio Marina de Chile" if rbd == 4531
replace nom_est = "Colegio Biobío" if rbd == 4548
replace nom_est = "Colegio Gran Bretaña" if rbd == 4572
replace nom_est = "Colegio John Kennedy" if rbd == 4575
replace nom_est = "Escuela Bélgica" if rbd == 4576
replace nom_est = "Escuela Darío Salas Marchant" if rbd == 4578
replace nom_est = "Liceo Rebeca Matte Bello" if rbd == 4585
replace nom_est = "Colegio República de Grecia" if rbd == 4591
replace nom_est = "Escuela Miguel José Zánartu Santa María" if rbd == 4594
replace nom_est = "Escuela Enrique Soro Barriga" if rbd == 4595
replace nom_est = "Escuela Básica Luis Alberto Acevedo" if rbd == 4611
replace nom_est = "Colegio Galvarino de Lomas Coloradas" if rbd == 4617
replace nom_est = "Colegio Particular Aurora de Chile" if rbd == 4627
replace nom_est = "Escuela Particular Pedro de Oña" if rbd == 4629
replace nom_est = "Colegio Edward" if rbd == 4665
replace nom_est = "Escuela Helen Keller Adams" if rbd == 4714
replace nom_est = "Escuela República del Perú" if rbd == 4719
replace nom_est = "Escuela Villa Independencia" if rbd == 4725
replace nom_est = "Escuela Alonkura" if rbd == 4730
replace nom_est = "Colegio Básico Villa Acero" if rbd == 4737
replace nom_est = "Escuela Básica Cerro San Francisco" if rbd == 4754
replace nom_est = "Escuela Isla de Pascua" if rbd == 4807
replace nom_est = "Escuela Básica Dichato" if rbd == 4834
replace nom_est = "Escuela Manuel Amat y Juniet" if rbd == 4898
replace nom_est = "Escuela Rosita Renard" if rbd == 4984
replace nom_est = "Escuela Rafael Sotomayor Baeza" if rbd == 4988
replace nom_est = "Escuela Víctor Domingo Silva" if rbd == 4989
replace nom_est = "Escuela Ambrosio O'Higgins" if rbd == 4990
replace nom_est = "Escuela Remigio Castro Aburto" if rbd == 4992
replace nom_est = "Escuela Adelaida Miguieles Soto" if rbd == 4994
replace nom_est = "Escuela Vista Hermosa" if rbd == 4996
replace nom_est = "Liceo Orlando Delgado Zúñiga" if rbd == 5113
replace nom_est = "Escuela Arturo Prat Chacón" if rbd == 5128
replace nom_est = "Colegio de Maipo" if rbd == 10640
replace nom_est = "Escuela Básica F-N°835 Hermanos Sánchez Cerda" if rbd == 10673
replace nom_est = "Liceo Municipal Poetisa Gabriela Mistral" if rbd == 10686
replace nom_est = "Colegio Niño Jesús" if rbd == 10713
replace nom_est = "Centro Educ. Part. María Reina Inmaculada" if rbd == 10734
replace nom_est = "Colegio Huilco Alto" if rbd == 10784
replace nom_est = "Escuela Lidia Matte Hurtado" if rbd == 10810
replace nom_est = "Escuela Maule" if rbd == 11398
replace nom_est = "Escuela Particular Gaspar Cabrales" if rbd == 11712
replace nom_est = "Colegio España" if rbd == 15731
replace nom_est = "Colegio María Escobillana Guzmán" if rbd == 15762
replace nom_est = "Escuela Divino Maestro" if rbd == 15770
replace nom_est = "Colegio Básico Nueva los Lobos" if rbd == 17693
replace nom_est = "Colegio Parroquial San José" if rbd == 17737
replace nom_est = "Colegio Pacific School" if rbd == 17779
replace nom_est = "Colegio Teresa de los Andes" if rbd == 17902
replace nom_est = "Escuela José Francisco Pino Medina" if rbd == 18002
replace nom_est = "Escuela Básica Forjadores de Chile" if rbd == 18015
replace nom_est = "Colegio San Agustín" if rbd == 18035
replace nom_est = "Centro Educacional Alborada" if rbd == 18127
replace nom_est = "Colegio Nuevos Horizontes" if rbd == 18218
replace nom_est = "Escuela Inmaculada Concepción" if rbd == 25255
replace nom_est = "Esc. Bas. y Esp. Centro Integral Altair de Ba" if rbd == 25288
replace nom_est = "Esc. Bas. y Esp. Nueva Integral Altazor" if rbd == 25624
replace nom_est = "Esc. Básica Municipal Paula Jaraquemada Alqui" if rbd == 25711
replace nom_est = "Colegio Nuestra Esperanza" if rbd == 40101
replace nom_est = "Escuela Blanca Estela Prat Carvajal" if rbd == 4722
replace nom_est = "Escuela Almirante Patricio Lynch" if rbd == 4811
replace nom_est = "Escuela Elias Sánchez Ortúzar" if rbd == 10668

replace region = 6 if rbd == 2456
replace region = 6 if rbd == 2115
replace region = 6 if rbd == 2493
replace region = 6 if rbd == 2166
replace region = 6 if rbd == 2487
replace region = 6 if rbd == 2139
replace region = 6 if rbd == 2363
replace region = 6 if rbd == 2210
replace region = 6 if rbd == 2489
replace region = 6 if rbd == 15770
replace region = 6 if rbd == 15731
replace region = 6 if rbd == 40101
replace region = 6 if rbd == 2458
replace region = 6 if rbd == 2707
replace region = 6 if rbd == 15762
replace region = 6 if rbd == 2206
replace region = 8 if rbd == 4043
replace region = 8 if rbd == 4984
replace region = 8 if rbd == 4629
replace region = 8 if rbd == 4898
replace region = 8 if rbd == 4455
replace region = 8 if rbd == 4576
replace region = 8 if rbd == 4275
replace region = 8 if rbd == 4992
replace region = 8 if rbd == 4989
replace region = 8 if rbd == 4996
replace region = 8 if rbd == 4585
replace region = 8 if rbd == 17779
replace region = 8 if rbd == 4141
replace region = 8 if rbd == 11398
replace region = 8 if rbd == 4990
replace region = 8 if rbd == 4988
replace region = 8 if rbd == 18002
replace region = 8 if rbd == 5113
replace region = 8 if rbd == 17902
replace region = 8 if rbd == 18015
replace region = 8 if rbd == 4811
replace region = 8 if rbd == 4594
replace region = 8 if rbd == 4730
replace region = 8 if rbd == 4665
replace region = 8 if rbd == 4737
replace region = 8 if rbd == 4714
replace region = 8 if rbd == 18127
replace region = 8 if rbd == 4531
replace region = 8 if rbd == 4719
replace region = 8 if rbd == 4617
replace region = 8 if rbd == 4052
replace region = 8 if rbd == 4548
replace region = 13 if rbd == 10810
replace region = 13 if rbd == 25255
replace region = 13 if rbd == 10668
replace region = 13 if rbd == 25711
replace region = 13 if rbd == 10673
replace region = 13 if rbd == 10713
replace region = 13 if rbd == 25288
replace region = 13 if rbd == 10686
replace region = 13 if rbd == 25624
replace region = 13 if rbd == 10784
replace region = 8 if rbd == 4725
replace region = 8 if rbd == 4754
replace region = 8 if rbd == 4611
replace region = 8 if rbd == 4578
replace region = 8 if rbd == 17693
replace region = 8 if rbd == 4595
replace region = 8 if rbd == 11712
replace region = 8 if rbd == 17737
replace region = 8 if rbd == 4591
replace region = 8 if rbd == 5128
replace region = 8 if rbd == 4807
replace region = 8 if rbd == 4627
replace region = 8 if rbd == 18218
replace region = 8 if rbd == 4994
replace region = 8 if rbd == 4572
replace region = 8 if rbd == 18035
replace region = 8 if rbd == 4834
replace region = 8 if rbd == 4722
replace region = 13 if rbd == 10734

drop student_firstname student_name student_lastname grade_range valid_rut grade total_questions section completion_status valid_age section_folder school_name
order folio region nom_est rbd curso letra tipo

gen con_negativo = 0
replace con_negativo = 1 if folio =="252554A13"
replace con_negativo = 1 if folio =="252554A14"
replace con_negativo = 1 if folio =="252554B32"
replace con_negativo = 1 if folio =="257114A1"
replace con_negativo = 1 if folio =="257114A15"
replace con_negativo = 1 if folio =="257115B36"
replace con_negativo = 1 if folio =="106864A1"
replace con_negativo = 1 if folio =="106864A7"
replace con_negativo = 1 if folio =="106864A12"
replace con_negativo = 1 if folio =="106864B1"
replace con_negativo = 1 if folio =="106864B4"
replace con_negativo = 1 if folio =="106864B6"
replace con_negativo = 1 if folio =="24567B9"
replace con_negativo = 1 if folio =="21154A14"
replace con_negativo = 1 if folio =="21664A12"
replace con_negativo = 1 if folio =="21664A23"
replace con_negativo = 1 if folio =="21666A27"
replace con_negativo = 1 if folio =="21666B1"
replace con_negativo = 1 if folio =="21666B4"
replace con_negativo = 1 if folio =="24874A15"
replace con_negativo = 1 if folio =="21394A1"
replace con_negativo = 1 if folio =="23637A13"
replace con_negativo = 1 if folio =="157705B9"
replace con_negativo = 1 if folio =="157705B11"
replace con_negativo = 1 if folio =="401015A9"
replace con_negativo = 1 if folio =="47376C2"
replace con_negativo = 1 if folio =="47376C16"
replace con_negativo = 1 if folio =="47377C2"
replace con_negativo = 1 if folio =="47377C13"
replace con_negativo = 1 if folio =="107137A11"
replace con_negativo = 1 if folio =="256245A6"
replace con_negativo = 1 if folio =="256245A5"
replace con_negativo = 1 if folio =="256245A7"
replace con_negativo = 1 if folio =="46655A3"


label define con_negativo 0 "falso", modify
label define con_negativo 1 "verdadero", modify
label variable con_negativo  "con_negativo. Consentimieno Negativo"









