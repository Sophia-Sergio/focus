capture program drop validate_rut
program define validate_rut, rclass
    version 15.0
    syntax varlist(string), GENerate(name) [replace]
    
    // Handle existing variable
    if "`replace'" != "" {
        capture drop `generate'
    }
    else {
        capture confirm variable `generate'
        if !_rc {
            exit 110
        }
    }
    
    quietly {
        foreach var of varlist `varlist' {
            // Clean the RUT
            gen str20 rut_clean = subinstr(subinstr(`var', ".", "", .), "-", "", .)
            
            // Split into number and check digit
            gen long rut_number = real(substr(rut_clean, 1, length(rut_clean)-1))
            gen str1 input_dv = upper(substr(rut_clean, -1, 1))
            
            // Calculate verification digit
            gen long sum = 0
            gen byte multiplier = 2
            gen long temp_num = rut_number
            
            // Chilean RUT algorithm
            while temp_num > 0 {
                replace sum = sum + mod(temp_num, 10) * multiplier
                replace temp_num = floor(temp_num / 10)
                replace multiplier = cond(multiplier == 7, 2, multiplier + 1)
            }
            
            gen byte remainder = mod(sum, 11)
            gen byte check_digit = 11 - remainder
            replace check_digit = 0 if check_digit == 11
            
            gen str1 calc_dv = cond(check_digit == 10, "K", string(check_digit))
            
            // Create validation result (1 = valid, 0 = invalid)
            gen byte `generate' = (input_dv == calc_dv) & !missing(rut_number) & rut_clean != ""
            
            // Clean up temporary variables
            drop rut_clean rut_number input_dv sum multiplier temp_num remainder check_digit calc_dv
        }
    }
    
    // Report results
    quietly count if `generate' == 1
    local valid_count = r(N)
    quietly count if `generate' == 0
    local invalid_count = r(N)
end


validate_rut rut, generate(valid_rut)

label variable valid_rut "Validacion Rut"

label define valid 0 "Inválido", modify
label define valid 1 "Válido", modify
label values valid_rut valid


