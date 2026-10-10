# District comparison queue

Implement these after the statewide basics. A district comparison would fit its own same-year, assessment, level and subject models, as CPS does. A filter using statewide predictions remains a district view of the statewide model; it is not a district comparison.

Size screen: official 2024-2025 CCD LEA membership, retrieved 2026-10-09. 75 first-tier and 172 second-tier new district candidates. The screen evaluates the 50 states; it excludes DC and territories. Source size and grade configuration do not establish usable assessment or income coverage.

## Selection and implementation gates

- First tier: at least 50,000 students and 30 potential pure grade schools or 30 potential pure high schools. Second tier: 20,000–49,999 students with the same cohort floor.
- Ordinary districts use native LEA types 1/2. Charter operators, supervisory unions, specialized agencies and regular districts with federal charter designations receive separate scope review.
- Potential ES/HS counts use operational schools, complete same-year reported grade offers and reconciled reported school membership. Grade schools have at least one grade 3–8 and no high-school grades; pure high schools have no lower grades. Mixed and ambiguous schools are not pooled into either count. These are configuration counts, not usable model counts.
- Before adding a comparison, verify at least 30 usable schools separately for Math, ELA and Combined in each proposed population. Report usable/profile coverage within that cohort, same-year income spread, leverage and exclusions. Thirty is a practical planning floor, not a guarantee of a stable regression.
- Resolve state source holds first. Audit exact school-to-district IDs, charter/alternative scope, source definitions, suppression and every-member interval availability. Never group by district name or merge unrelated districts to reach the floor.
- Prioritize larger usable cohorts after their audits. Preserve existing CPS and NYC models. State and district residuals describe different comparison populations and must remain explicitly labeled.

## First tier · largest new district comparisons

| District | State | NCES LEA | Students | Potential ES / HS | State source status |
| --- | --- | --- | ---: | ---: | --- |
| BROWARD | FL | 1200180 | 243,553 | 243 / 45 | Available; district audit pending |
| HILLSBOROUGH | FL | 1200870 | 220,360 | 218 / 34 | Available; district audit pending |
| ORANGE | FL | 1201440 | 205,853 | 206 / 31 | Available; district audit pending |
| PALM BEACH | FL | 1201500 | 189,634 | 168 / 26 | Available; district audit pending |
| Gwinnett County | GA | 1302550 | 182,518 | 111 / 24 | Available; district audit pending |
| Fairfax County Public Schools | VA | 5101260 | 179,323 | 162 / 25 | Available; district audit pending |
| HOUSTON ISD | TX | 4823640 | 176,727 | 212 / 42 | Available; district audit pending |
| Wake County Schools | NC | 3704720 | 163,325 | 162 / 29 | Available; district audit pending |
| Montgomery County Public Schools | MD | 2400480 | 159,181 | 172 / 25 | Available; district audit pending |
| Charlotte-Mecklenburg Schools | NC | 3702970 | 147,299 | 146 / 25 | Available; district audit pending |
| DALLAS ISD | TX | 4816230 | 139,802 | 189 / 37 | Available; district audit pending |
| Prince George's County Public Schools | MD | 2400510 | 132,123 | 160 / 23 | Available; district audit pending |
| DUVAL | FL | 1200480 | 130,054 | 151 / 24 | Available; district audit pending |
| Philadelphia City SD | PA | 4218990 | 120,057 | 162 / 47 | Available; district audit pending |
| CYPRESS-FAIRBANKS ISD | TX | 4816110 | 117,927 | 78 / 13 | Available; district audit pending |
| POLK | FL | 1201590 | 111,372 | 110 / 16 | Available; district audit pending |
| Memphis-Shelby County Schools | TN | 4700148 | 111,124 | 154 / 36 | Available; district audit pending |
| Baltimore County Public Schools | MD | 2400120 | 110,024 | 139 / 30 | Available; district audit pending |
| Cobb County | GA | 1301290 | 105,738 | 90 / 16 | Available; district audit pending |
| LEE | FL | 1201080 | 102,506 | 78 / 21 | Available; district audit pending |
| NORTHSIDE ISD | TX | 4833120 | 100,208 | 107 / 16 | Available; district audit pending |
| KATY ISD | TX | 4825170 | 96,111 | 65 / 11 | Available; district audit pending |
| Jefferson County | KY | 2102990 | 95,180 | 114 / 2 | State source hold |
| San Diego Unified | CA | 0634320 | 95,175 | 143 / 23 | Available; district audit pending |
| DeKalb County | GA | 1301740 | 91,752 | 103 / 21 | Available; district audit pending |
| School District No. 1 in the county of Denver and State of C | CO | 0803360 | 90,471 | 138 / 43 | Available; district audit pending |
| Prince William County Public Schools | VA | 5103130 | 90,242 | 82 / 8 | Available; district audit pending |
| PINELLAS | FL | 1201560 | 87,876 | 111 / 18 | Available; district audit pending |
| Fulton County | GA | 1302280 | 87,019 | 82 / 21 | Available; district audit pending |
| Alpine District | UT | 4900030 | 86,645 | 60 / 10 | State source hold |
| PASCO | FL | 1201530 | 86,627 | 75 / 13 | Available; district audit pending |
| Anne Arundel County Public Schools | MD | 2400060 | 85,029 | 99 / 15 | Available; district audit pending |
| Davidson County | TN | 4703180 | 81,021 | 118 / 26 | Available; district audit pending |
| FORT BEND ISD | TX | 4819650 | 79,663 | 67 / 13 | Available; district audit pending |
| Greenville 01 | SC | 4502310 | 77,774 | 70 / 15 | Available; district audit pending |
| Baltimore City Public Schools | MD | 2400090 | 76,807 | 114 / 23 | Available; district audit pending |
| OSCEOLA | FL | 1201470 | 75,314 | 57 / 10 | Available; district audit pending |
| ALBUQUERQUE | NM | 3500060 | 74,792 | 125 / 28 | Available; district audit pending |
| Jefferson County School District No. R-1 | CO | 0804800 | 73,532 | 103 / 21 | Available; district audit pending |
| CONROE ISD | TX | 4815000 | 72,914 | 56 / 7 | Available; district audit pending |
| AUSTIN ISD | TX | 4808940 | 72,272 | 97 / 17 | Available; district audit pending |
| Davis District | UT | 4900210 | 71,428 | 63 / 10 | State source hold |
| BREVARD | FL | 1200150 | 71,198 | 78 / 6 | Available; district audit pending |
| FORT WORTH ISD | TX | 4819700 | 70,405 | 99 / 20 | Available; district audit pending |
| Fresno Unified | CA | 0614550 | 68,131 | 84 / 13 | Available; district audit pending |
| Guilford County Schools | NC | 3701920 | 67,620 | 86 / 24 | Available; district audit pending |
| Milwaukee School District | WI | 5509600 | 65,599 | 113 / 26 | Available; district audit pending |
| FRISCO ISD | TX | 4820010 | 65,289 | 62 / 13 | Available; district audit pending |
| Washoe County | NV | 3200480 | 64,244 | 91 / 7 | Available; district audit pending |
| Chesterfield County Public Schools | VA | 5100840 | 64,194 | 53 / 11 | Available; district audit pending |
| SEMINOLE | FL | 1201710 | 63,934 | 54 / 9 | Available; district audit pending |
| Elk Grove Unified | CA | 0612330 | 63,421 | 52 / 12 | Available; district audit pending |
| Long Beach Unified | CA | 0622500 | 62,644 | 68 / 13 | Available; district audit pending |
| VOLUSIA | FL | 1201920 | 61,724 | 60 / 7 | Available; district audit pending |
| Douglas County School District No. Re 1 | CO | 0803450 | 61,243 | 68 / 13 | Available; district audit pending |
| Knox County | TN | 4702220 | 60,185 | 68 / 16 | Available; district audit pending |
| Granite District | UT | 4900360 | 59,106 | 67 / 5 | State source hold |
| Jordan District | UT | 4900420 | 58,788 | 44 / 8 | State source hold |
| Howard County Public Schools | MD | 2400420 | 57,565 | 62 / 13 | Available; district audit pending |
| NORTH EAST ISD | TX | 4832940 | 56,420 | 61 / 11 | Available; district audit pending |
| ALDINE ISD | TX | 4807710 | 56,419 | 49 / 10 | Available; district audit pending |
| Forsyth County | GA | 1302220 | 54,864 | 34 / 8 | Available; district audit pending |
| MANATEE | FL | 1201230 | 54,215 | 56 / 3 | Available; district audit pending |
| ARLINGTON ISD | TX | 4808700 | 53,339 | 62 / 8 | Available; district audit pending |
| OMAHA PUBLIC SCHOOLS | NE | 3174820 | 52,524 | 78 / 9 | State source hold |
| KLEIN ISD | TX | 4825740 | 52,437 | 42 / 5 | Available; district audit pending |
| Winston Salem / Forsyth County Schools | NC | 3701500 | 52,430 | 59 / 14 | Available; district audit pending |
| ST. JOHNS | FL | 1201740 | 52,324 | 35 / 3 | Available; district audit pending |
| Rutherford County | TN | 4703690 | 52,127 | 39 / 9 | Available; district audit pending |
| Cherry Creek School District No. 5 in the county of Arapah | CO | 0802910 | 51,980 | 57 / 7 | Available; district audit pending |
| Clayton County | GA | 1301230 | 51,055 | 52 / 11 | Available; district audit pending |
| GARLAND ISD | TX | 4820340 | 51,021 | 56 / 7 | Available; district audit pending |
| Henrico County Public Schools | VA | 5101890 | 50,915 | 57 / 9 | Available; district audit pending |
| Charleston 01 | SC | 4501440 | 50,856 | 61 / 10 | Available; district audit pending |
| Seattle School District No. 1 | WA | 5307710 | 50,773 | 85 / 16 | Available; district audit pending |

## Second tier · substantial regional comparisons

| District | State | NCES LEA | Students | Potential ES / HS | State source status |
| --- | --- | --- | ---: | ---: | --- |
| Mobile County | AL | 0102370 | 49,946 | 66 / 10 | Available; district audit pending |
| Atlanta Public Schools | GA | 1300120 | 49,945 | 70 / 11 | Available; district audit pending |
| Corona-Norco Unified | CA | 0609850 | 49,487 | 41 / 8 | Available; district audit pending |
| ST. LUCIE | FL | 1201770 | 49,308 | 34 / 5 | Available; district audit pending |
| Cumberland County Schools | NC | 3700011 | 49,002 | 63 / 16 | Available; district audit pending |
| San Francisco Unified | CA | 0634410 | 48,902 | 85 / 15 | Available; district audit pending |
| Horry 01 | SC | 4502490 | 48,662 | 41 / 11 | Available; district audit pending |
| HUMBLE ISD | TX | 4823910 | 48,502 | 40 / 7 | Available; district audit pending |
| COLLIER | FL | 1200330 | 48,252 | 48 / 9 | Available; district audit pending |
| EL PASO ISD | TX | 4818300 | 48,118 | 58 / 13 | Available; district audit pending |
| Frederick County Public Schools | MD | 2400330 | 48,054 | 52 / 10 | Available; district audit pending |
| LAKE | FL | 1201050 | 47,982 | 39 / 10 | Available; district audit pending |
| LEWISVILLE ISD | TX | 4827300 | 47,876 | 54 / 5 | Available; district audit pending |
| ROUND ROCK ISD | TX | 4838080 | 46,954 | 47 / 8 | Available; district audit pending |
| Jefferson Parish | LA | 2200840 | 46,790 | 57 / 9 | Available; district audit pending |
| LAMAR CISD | TX | 4826580 | 46,786 | 39 / 7 | Available; district audit pending |
| SOCORRO ISD | TX | 4840710 | 46,668 | 41 / 9 | Available; district audit pending |
| PLANO ISD | TX | 4835100 | 46,612 | 57 / 11 | Available; district audit pending |
| Columbus City Schools District | OH | 3904380 | 46,515 | 90 / 18 | State source hold |
| PASADENA ISD | TX | 4834320 | 46,491 | 58 / 8 | Available; district audit pending |
| MARION | FL | 1201260 | 46,352 | 44 / 8 | Available; district audit pending |
| Boston | MA | 2502790 | 46,094 | 70 / 6 | Available; district audit pending |
| Wichita | KS | 2012990 | 46,073 | 68 / 10 | Available; district audit pending |
| Hamilton County | TN | 4701590 | 45,981 | 58 / 14 | Available; district audit pending |
| SARASOTA | FL | 1201680 | 45,246 | 42 / 6 | Available; district audit pending |
| Newark Public School District | NJ | 3411340 | 44,199 | 45 / 16 | Available; district audit pending |
| San Bernardino City Unified | CA | 0634170 | 44,192 | 60 / 9 | Available; district audit pending |
| SAN ANTONIO ISD | TX | 4838730 | 44,047 | 61 / 14 | Available; district audit pending |
| Nebo District | UT | 4900630 | 43,696 | 35 / 1 | State source hold |
| Clovis Unified | CA | 0609030 | 43,669 | 41 / 6 | Available; district audit pending |
| Portland SD 1J | OR | 4110040 | 43,357 | 66 / 10 | Available; district audit pending |
| Henry County | GA | 1302820 | 43,012 | 41 / 11 | Available; district audit pending |
| KILLEEN ISD | TX | 4825660 | 42,883 | 45 / 9 | Available; district audit pending |
| LEANDER ISD | TX | 4827030 | 42,608 | 39 / 8 | Available; district audit pending |
| Anchorage School District | AK | 0200180 | 42,573 | 71 / 11 | Available; district audit pending |
| LINCOLN PUBLIC SCHOOLS | NE | 3172840 | 42,301 | 52 / 8 | State source hold |
| Fayette County | KY | 2101860 | 42,138 | 53 / 2 | State source hold |
| Cherokee County | GA | 1301110 | 42,031 | 30 / 7 | Available; district audit pending |
| Williamson County | TN | 4704530 | 41,593 | 41 / 11 | Available; district audit pending |
| Chandler Unified District #80 (4242) | AZ | 0401870 | 41,421 | 37 / 2 | Available; district audit pending |
| Union County Public Schools | NC | 3704620 | 41,404 | 38 / 10 | Available; district audit pending |
| UNITED ISD | TX | 4843650 | 40,742 | 43 / 4 | Available; district audit pending |
| Chesapeake City Public Schools | VA | 5100810 | 40,607 | 31 / 7 | Available; district audit pending |
| Capistrano Unified | CA | 0607440 | 40,358 | 49 / 3 | Available; district audit pending |
| Tucson Unified District (4403) | AZ | 0408800 | 40,316 | 61 / 2 | Available; district audit pending |
| CLEAR CREEK ISD | TX | 4814280 | 39,684 | 37 / 8 | Available; district audit pending |
| San Juan Unified | CA | 0634620 | 39,446 | 50 / 12 | Available; district audit pending |
| Berkeley 01 | SC | 4501170 | 39,423 | 35 / 8 | Available; district audit pending |
| Montgomery County | TN | 4703030 | 39,385 | 32 / 10 | Available; district audit pending |
| East Baton Rouge Parish | LA | 2200540 | 39,320 | 60 / 10 | Available; district audit pending |
| CLAY | FL | 1200300 | 39,122 | 35 / 1 | Available; district audit pending |
| JOINT SCHOOL DISTRICT NO. 2 | ID | 1602100 | 38,740 | 46 / 12 | Available; district audit pending |
| Aurora Joint District No. 28 of the counties of Adams and A | CO | 0802340 | 38,702 | 43 / 6 | Available; district audit pending |
| ALIEF ISD | TX | 4807830 | 38,610 | 37 / 5 | Available; district audit pending |
| Anoka-Hennepin School District | MN | 2703180 | 38,354 | 31 / 11 | Available; district audit pending |
| Riverside Unified | CA | 0633150 | 38,033 | 36 / 7 | Available; district audit pending |
| Irvine Unified | CA | 0684500 | 38,028 | 36 / 6 | Available; district audit pending |
| Salem-Keizer SD 24J | OR | 4110820 | 37,982 | 57 / 7 | Available; district audit pending |
| MESQUITE ISD | TX | 4830390 | 37,930 | 44 / 7 | Available; district audit pending |
| Sacramento City Unified | CA | 0633840 | 37,913 | 59 / 11 | Available; district audit pending |
| Beaverton SD 48J | OR | 4101920 | 37,891 | 30 / 7 | Available; district audit pending |
| Harford County Public Schools | MD | 2400390 | 37,771 | 42 / 10 | Available; district audit pending |
| Johnston County Public Schools | NC | 3702370 | 37,320 | 36 / 7 | Available; district audit pending |
| Garden Grove Unified | CA | 0614880 | 37,009 | 48 / 7 | Available; district audit pending |
| RICHARDSON ISD | TX | 4837020 | 36,971 | 44 / 4 | Available; district audit pending |
| Washington District | UT | 4901140 | 36,961 | 34 / 5 | State source hold |
| ESCAMBIA | FL | 1200510 | 36,768 | 45 / 8 | Available; district audit pending |
| BROWNSVILLE ISD | TX | 4811680 | 36,140 | 41 / 7 | Available; district audit pending |
| Santa Ana Unified | CA | 0635310 | 36,036 | 40 / 8 | Available; district audit pending |
| St. Tammany Parish | LA | 2201650 | 35,956 | 42 / 8 | Available; district audit pending |
| Savannah-Chatham County | GA | 1301020 | 35,744 | 41 / 9 | Available; district audit pending |
| Jefferson County | AL | 0101920 | 35,444 | 38 / 10 | Available; district audit pending |
| MANSFIELD ISD | TX | 4828920 | 35,354 | 38 / 8 | Available; district audit pending |
| Cincinnati Public Schools | OH | 3904375 | 34,531 | 40 / 1 | State source hold |
| Adams 12 Five Star Schools | CO | 0806900 | 34,466 | 41 / 6 | Available; district audit pending |
| Peoria Unified School District (4237) | AZ | 0406250 | 34,436 | 33 / 0 | Available; district audit pending |
| Poway Unified | CA | 0631530 | 34,405 | 32 / 7 | Available; district audit pending |
| YSLETA ISD | TX | 4846680 | 34,062 | 35 / 10 | Available; district audit pending |
| Oakland Unified | CA | 0628050 | 33,838 | 59 / 14 | Available; district audit pending |
| ECTOR COUNTY ISD | TX | 4818000 | 33,663 | 32 / 5 | Available; district audit pending |
| Stockton Unified | CA | 0638010 | 33,648 | 41 / 9 | Available; district audit pending |
| TULSA | OK | 4030240 | 33,617 | 58 / 11 | Available; district audit pending |
| SPRING ISD | TX | 4841220 | 33,590 | 34 / 6 | Available; district audit pending |
| EDINBURG CISD | TX | 4818180 | 33,343 | 37 / 5 | Available; district audit pending |
| DENTON ISD | TX | 4816740 | 33,329 | 35 / 6 | Available; district audit pending |
| Cleveland Municipal | OH | 3904378 | 33,143 | 52 / 26 | State source hold |
| Fremont Unified | CA | 0614400 | 33,134 | 33 / 7 | Available; district audit pending |
| CORPUS CHRISTI ISD | TX | 4815270 | 33,103 | 42 / 8 | Available; district audit pending |
| Saint Paul Public Schools | MN | 2733840 | 33,041 | 50 / 9 | Available; district audit pending |
| Fontana Unified | CA | 0613920 | 32,794 | 37 / 7 | Available; district audit pending |
| OKLAHOMA CITY | OK | 4022770 | 32,750 | 46 / 10 | Available; district audit pending |
| Canyons District | UT | 4900142 | 32,688 | 37 / 1 | State source hold |
| SPRING BRANCH ISD | TX | 4841100 | 32,668 | 32 / 5 | Available; district audit pending |
| Deer Valley Unified District (4246) | AZ | 0407750 | 32,265 | 34 / 0 | Available; district audit pending |
| Caddo Parish | LA | 2200300 | 32,165 | 40 / 6 | Available; district audit pending |
| NORTHWEST ISD | TX | 4833180 | 32,098 | 30 / 7 | Available; district audit pending |
| Weber District | UT | 4901200 | 32,054 | 32 / 5 | State source hold |
| KELLER ISD | TX | 4825260 | 32,042 | 33 / 6 | Available; district audit pending |
| Baldwin County | AL | 0100270 | 31,965 | 33 / 7 | Available; district audit pending |
| Durham Public Schools | NC | 3701260 | 31,865 | 41 / 6 | Available; district audit pending |
| LEON | FL | 1201110 | 31,645 | 36 / 6 | Available; district audit pending |
| St. Vrain Valley School District No. Re1J | CO | 0805370 | 31,607 | 41 / 9 | Available; district audit pending |
| Gilbert Unified District (4239) | AZ | 0403400 | 31,560 | 31 / 0 | Available; district audit pending |
| Gaston County Schools | NC | 3701620 | 30,995 | 38 / 11 | Available; district audit pending |
| Lake Washington School District | WA | 5304230 | 30,986 | 44 / 7 | Available; district audit pending |
| Sumner County | TN | 4704020 | 30,719 | 39 / 11 | Available; district audit pending |
| Des Moines Independent Comm School District | IA | 1908970 | 30,048 | 48 / 6 | Available; district audit pending |
| Minneapolis Public School District | MN | 2721240 | 29,928 | 46 / 25 | Available; district audit pending |
| PHARR-SAN JUAN-ALAMO ISD | TX | 4834860 | 29,613 | 33 / 6 | Available; district audit pending |
| Mt. Diablo Unified | CA | 0626370 | 29,494 | 40 / 7 | Available; district audit pending |
| Lafayette Parish | LA | 2200870 | 29,396 | 34 / 7 | Available; district audit pending |
| Poudre School District R-1 | CO | 0803990 | 29,381 | 39 / 5 | Available; district audit pending |
| Muscogee County | GA | 1303870 | 29,362 | 42 / 8 | Available; district audit pending |
| AMARILLO ISD | TX | 4808130 | 29,321 | 48 / 6 | Available; district audit pending |
| Richmond County | GA | 1304380 | 28,923 | 37 / 8 | Available; district audit pending |
| Spokane School District | WA | 5308250 | 28,853 | 46 / 9 | Available; district audit pending |
| Tacoma School District | WA | 5308700 | 28,847 | 49 / 12 | Available; district audit pending |
| Visalia Unified | CA | 0641160 | 28,809 | 33 / 6 | Available; district audit pending |
| San Ramon Valley Unified | CA | 0635130 | 28,615 | 30 / 5 | Available; district audit pending |
| Fort Wayne Community Schools | IN | 1803630 | 28,549 | 40 / 5 | Available; district audit pending |
| Rockford SD 205 | IL | 1734510 | 28,467 | 35 / 4 | Available; district audit pending |
| Bakersfield City | CA | 0603630 | 28,365 | 44 / 0 | Available; district audit pending |
| ALACHUA | FL | 1200030 | 28,204 | 40 / 4 | Available; district audit pending |
| Olathe | KS | 2010140 | 28,195 | 46 / 0 | Available; district audit pending |
| Charles County Public Schools | MD | 2400270 | 28,162 | 31 / 7 | Available; district audit pending |
| Boulder Valley School District No. Re2 | CO | 0802490 | 27,988 | 43 / 8 | Available; district audit pending |
| Arlington County Public Schools | VA | 5100270 | 27,950 | 31 / 4 | Available; district audit pending |
| Calcasieu Parish | LA | 2200330 | 27,851 | 41 / 8 | Available; district audit pending |
| Onslow County Schools | NC | 3703450 | 27,551 | 30 / 8 | Available; district audit pending |
| Lodi Unified | CA | 0622230 | 27,109 | 36 / 7 | Available; district audit pending |
| Norfolk City Public Schools | VA | 5102670 | 26,807 | 35 / 5 | Available; district audit pending |
| Shawnee Mission Pub Sch | KS | 2011640 | 26,513 | 39 / 5 | Available; district audit pending |
| Livingston Parish | LA | 2201020 | 26,499 | 32 / 5 | Available; district audit pending |
| Paradise Valley Unified District (4241) | AZ | 0405930 | 26,183 | 34 / 0 | Available; district audit pending |
| Carroll County Public Schools | MD | 2400210 | 26,141 | 31 / 10 | Available; district audit pending |
| Jersey City Public Schools | NJ | 3407830 | 25,951 | 30 / 7 | Available; district audit pending |
| Newport News City Public Schools | VA | 5102640 | 25,882 | 31 / 5 | Available; district audit pending |
| Academy School District No. 20 in the county of El Paso an | CO | 0801920 | 25,607 | 30 / 8 | Available; district audit pending |
| Kent School District | WA | 5303960 | 25,358 | 36 / 6 | Available; district audit pending |
| West Contra Costa Unified | CA | 0632550 | 25,244 | 43 / 8 | Available; district audit pending |
| New Hanover County Schools | NC | 3703330 | 25,155 | 33 / 5 | Available; district audit pending |
| Madison Metropolitan School District | WI | 5508520 | 25,155 | 40 / 7 | Available; district audit pending |
| Sioux Falls School District 49-5 | SD | 4666270 | 25,051 | 31 / 6 | State source hold |
| Twin Rivers Unified | CA | 0601332 | 24,849 | 35 / 7 | Available; district audit pending |
| Worcester | MA | 2513230 | 24,778 | 38 / 1 | Available; district audit pending |
| San Jose Unified | CA | 0634590 | 24,453 | 33 / 7 | Available; district audit pending |
| Paterson Public School District | NJ | 3412690 | 24,291 | 32 / 9 | Available; district audit pending |
| SPRINGFIELD R-XII | MO | 2928860 | 24,285 | 43 / 4 | Available; district audit pending |
| Huntsville City | AL | 0101800 | 24,222 | 36 / 6 | Available; district audit pending |
| CARROLLTON-FARMERS BRANCH ISD | TX | 4813050 | 24,165 | 30 / 6 | Available; district audit pending |
| LUBBOCK ISD | TX | 4828500 | 24,133 | 37 / 5 | Available; district audit pending |
| Orange Unified | CA | 0628650 | 23,823 | 31 / 5 | Available; district audit pending |
| Springfield | MA | 2511130 | 23,670 | 47 / 10 | Available; district audit pending |
| MOORE | OK | 4020250 | 23,567 | 31 / 3 | Available; district audit pending |
| MILLARD PUBLIC SCHOOLS | NE | 3173740 | 23,253 | 31 / 3 | State source hold |
| Kanawha County Schools | WV | 5400600 | 23,085 | 50 / 8 | State source hold |
| LA JOYA ISD | TX | 4826130 | 22,942 | 30 / 5 | Available; district audit pending |
| Aiken 01 | SC | 4500720 | 22,916 | 32 / 7 | Available; district audit pending |
| LAS CRUCES | NM | 3501500 | 22,782 | 32 / 6 | Available; district audit pending |
| Washington County Public Schools | MD | 2400660 | 22,772 | 31 / 8 | Available; district audit pending |
| Buncombe County Schools | NC | 3700450 | 22,452 | 33 / 3 | Available; district audit pending |
| Blue Valley | KS | 2012000 | 22,252 | 31 / 6 | Available; district audit pending |
| Chula Vista Elementary | CA | 0608610 | 22,245 | 43 / 0 | Available; district audit pending |
| Colorado Springs School District No. 11 in the county of E | CO | 0803060 | 22,227 | 47 / 9 | Available; district audit pending |
| BOISE INDEPENDENT DISTRICT | ID | 1600360 | 22,134 | 34 / 4 | Available; district audit pending |
| Richland 01 | SC | 4503360 | 21,814 | 38 / 8 | Available; district audit pending |
| Kansas City | KS | 2007950 | 21,538 | 35 / 3 | Available; district audit pending |
| Rapides Parish | LA | 2201290 | 21,340 | 30 / 5 | Available; district audit pending |
| Public Schools of Robeson County | NC | 3703930 | 21,301 | 30 / 5 | Available; district audit pending |
| Toledo City | OH | 3904490 | 21,290 | 40 / 6 | State source hold |
| Indianapolis Public Schools | IN | 1804770 | 21,055 | 41 / 0 | Available; district audit pending |
| Birmingham City | AL | 0100390 | 20,954 | 35 / 7 | Available; district audit pending |

## Existing comparisons and components

CPS, Los Angeles Unified, Miami-Dade grade schools and Clark County native grade schools are implemented. Hawaii’s single state LEA already has its statewide comparison. The NYC geographic LEAs below are components of the existing NYC system; they would be optional subdistrict work, not additional whole-city systems. Do not add their counts to the Chancellor’s Office supervisory total or include District 75 or administrative charter category 84 as ordinary geographic districts.

## Existing scope · size references

| District | State | NCES LEA | Students | Potential ES / HS | State source status |
| --- | --- | --- | ---: | ---: | --- |
| Los Angeles Unified | CA | 0622710 | 408,026 | 572 / 147 | Existing Los Angeles Unified comparison; pure cohorts |
| MIAMI-DADE | FL | 1200390 | 333,233 | 365 / 81 | Existing Miami-Dade comparison; pure grade schools only |
| Chicago Public Schools Dist 299 | IL | 1709930 | 324,130 | 303 / 125 | Existing CPS comparison; size reference |
| Clark County | NV | 3200060 | 306,038 | 296 / 10 | Existing Clark County comparison; native grade-school scope only |
| Hawaii Department of Education | HI | 1500030 | 167,071 | 224 / 2 | Existing statewide comparison |
| NEW YORK CITY GEOGRAPHIC DISTRICT #31 | NY | 3600103 | 60,164 | 35 / 3 | Optional NYC subdistrict audit |
| NEW YORK CITY GEOGRAPHIC DISTRICT # 2 | NY | 3600077 | 55,345 | 34 / 50 | Optional NYC subdistrict audit |
| NEW YORK CITY GEOGRAPHIC DISTRICT #24 | NY | 3600098 | 50,026 | 17 / 10 | NYC component; cohort floor review |

## Scope or cohort review

These agencies meet the district-size/cohort screen, or have at least 50,000 students but fewer than 30 potential schools in either pure cohort. Their scope needs a separate decision before entering the ordinary district queue.

| Agency | State | NCES LEA | Students | Potential ES / HS | Review reason |
| --- | --- | --- | ---: | ---: | --- |
| Loudoun County Public Schools | VA | 5102250 | 81,486 | 79 / 12 | Regular district; federal charter designation needs scope review |
| IDEA PUBLIC SCHOOLS | TX | 4800211 | 79,430 | 64 / 0 | Independent charter district |
| Virginia Beach City Public Schools | VA | 5103840 | 64,731 | 69 / 11 | Regular district; federal charter designation needs scope review |
| State Sponsored Charter Schools | NV | 3200001 | 63,609 | 47 / 14 | Independent charter district |
| Mesa Unified District (4235) | AZ | 0404970 | 55,821 | 28 / 7 | Fewer than 30 potential schools in either pure cohort |
| KIPP TEXAS PUBLIC SCHOOLS | TX | 4800264 | 32,771 | 37 / 9 | Independent charter district |
| Montgomery County | AL | 0102430 | 26,395 | 38 / 7 | Regular district; federal charter designation needs scope review |
| INTERNATIONAL LEADERSHIP OF TEXAS (ILTEXAS) | TX | 4801440 | 25,497 | 36 / 8 | Independent charter district |
| UPLIFT EDUCATION | TX | 4800030 | 23,384 | 32 / 13 | Independent charter district |
| Richmond City Public Schools | VA | 5103240 | 20,962 | 33 / 8 | Regular district; federal charter designation needs scope review |

## Additional native-source follow-up

Detroit Public Schools Community District (Michigan; NCES LEA `2601103`) warrants follow-up beyond the conservative CCD configuration screen. The [Michigan native audit](michigan-data.md#district-follow-up) resolves grade-school configuration, but current usable Math and Combined cohorts fall below the 30-school implementation floor. It remains a district source/cohort hold; it is not included in the CCD-only candidate totals above.


## District source and model audits

The [Los Angeles Unified roster and model audits](los-angeles-district.md) use exact official CCD school membership and same-year California records. They retain charter and alternative-school flags, separate mixed-grade schools, and document subject exclusions. The district region uses separate audited fits; statewide California remains its own comparison.

The [Miami-Dade roster and numerical audits](miami-dade-district.md) keep exact CCD district membership separate from Florida's native enrolled-grade school population. They document offered-versus-enrolled grade differences, raw individual lunch eligibility, collocated/virtual exclusions and missing score counts. The district region uses independently checked pure grade-school fits with no sampling intervals; high-school and mixed assessment scope remain unaudited. Statewide Florida remains its own comparison.

The [Clark County source, numerical and integration audits](clark-county-district.md) retain exact Nevada LEA 3200060 / NV-02 membership and the reported-zero ungraded-enrollment safeguard. The region retains 289 native source profiles with independent 286-school Math, ELA and Combined district models. All 299 native lower configurations and wider operational exclusions remain auditable. Valid-score counts and sampling intervals are unavailable; high-school and mixed assessment scope remains unaudited. Statewide Nevada remains its own comparison.

The [Broward source/cohort and numerical audits](broward-district.md) retain exact Florida LEA 1200180 / FL-06 membership, same-year individual lunch eligibility and native School Grades records. Offered and enrolled grade populations, source exclusions and missing records remain explicit. Three independent 241-school district fits retain external studentization and influence diagnostics without sampling intervals. Both historical audits keep approval false; canonical import and browser integration remain pending. Broward remains in the planning queue and no comparison is enabled.


## Provenance and rebuild

Enrollment uses the native LEA **Education Unit Total**, with `DMS_FLAG=Reported`; it is not a sum of school enrollment and is never a tested-score denominator. Every included agency retains its native raw directory/total records and source-row numbers. Reconstructed operational counts from the school directory remain separate from the native LEA operational-school field. The extract retains exact potential school IDs, source URLs and SHA-256 hashes. It is a planning artifact and never enables a browser comparison.

[Machine-readable planning extract](../data/source/district-comparison-candidates.json) · [State expansion status](state-expansion.md) · [State source holds](expansion-blockers.md)

- [lea directory](<https://nces.ed.gov/ccd/Data/zip/ccd_lea_029_2425_w_1a_073025.zip>) · SHA-256 `2745169e4bc7cd53adff179830c3d4b9bb035ac79580ecea01ef389a161936a9`
- [lea membership](<https://nces.ed.gov/ccd/Data/zip/ccd_lea_052_2425_l_1a_073025.zip>) · SHA-256 `501d72720a01c26e0e041cd3b1aa6653d0a94725ba0a1e85c42c4f183bc627ba`
- [school directory](<https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip>) · SHA-256 `39326da788aa322353d20ceaf8ad4baed26272502cd05b066cf6c594988b21ab`
- [school membership](<https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip>) · SHA-256 `4a7f660c5fc5eaae488dd02fd43498f349fc828b227edd0970d5b6995ead4d4d`
- [lea directory companion](<https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Directory_Companion_2026-005d.xlsx>) · SHA-256 `6af2133f3d40ecbcb3a03dcb4a60a7d312f89d23a0bf6c2e704b6a0144a28a71`
- [lea membership companion](<https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Membership_Companion_2026-005d.xlsx>) · SHA-256 `cff1d39788eedda41fe2af783e1e9e6c63c0c64e6e5ed5d925c67da64c2643e2`

```sh
.venv/bin/python scripts/plan_district_comparisons.py            # render committed extract offline
.venv/bin/python scripts/plan_district_comparisons.py --extract  # re-screen downloaded CCD files
```
