# First-tier district issues

This index records the 66 first-tier issues created as [large-district work under #3](https://github.com/robot-assisted-projects/FRPL-RMA/issues/3). The exact identities and publication checkpoint are retained in [the issue registry](../data/source/district-issue-work.json). Names and identifiers below follow that registry.

At the recorded creation checkpoint, all 66 issues are open and none is completed. Charlotte-Mecklenburg [#19](https://github.com/robot-assisted-projects/FRPL-RMA/issues/19) is the only issue with a completed source/cohort phase, at [fd62bf7](https://github.com/robot-assisted-projects/FRPL-RMA/commit/fd62bf7e67f3be9257973b5a1e117b0f87667ac3). Its immutable [source audit](https://github.com/robot-assisted-projects/FRPL-RMA/blob/fd62bf7e67f3be9257973b5a1e117b0f87667ac3/data/source/charlotte-district-audit.json) and [guide](https://github.com/robot-assisted-projects/FRPL-RMA/blob/fd62bf7e67f3be9257973b5a1e117b0f87667ac3/docs/charlotte-district.md) record that work. Charlotte’s numerical, canonical/static integration, tests/browser and master-delivery gates remain pending; the other 65 district audits have not started.

Native attachment to parent #3 is verified only for #19. The other 65 attachments await account access. After the successful issue creations and Charlotte attachment check, both the GitHub CLI and connector returned HTTP 403, “Sorry. Your account was suspended” for robotic-assistants. No complete post-creation inventory refresh was possible; creation readbacks are recorded for every issue. The pending attachments must be completed and verified when access returns.

All 172 second-tier candidates are paused under [#18](https://github.com/robot-assisted-projects/FRPL-RMA/issues/18) until further discussion. Existing source holds are reused: [Kentucky #5](https://github.com/robot-assisted-projects/FRPL-RMA/issues/5), [Nebraska #6](https://github.com/robot-assisted-projects/FRPL-RMA/issues/6), [Utah #11](https://github.com/robot-assisted-projects/FRPL-RMA/issues/11) and [Texas scored-count verification #16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16). [Detroit #15](https://github.com/robot-assisted-projects/FRPL-RMA/issues/15) remains a separate existing cohort hold outside these 66 issues. A linked hold in the table records a dependency, not modeling approval.

A district reaches `master` only after its source/cohort, independent numerical, canonical/static integration, repeatability, tests/browser and independent review gates are complete. Source-only work does not complete a district issue.

| Issue | District | State | NCES LEA | Native LEA | Linked hold |
| --- | --- | --- | --- | --- | --- |
| [#19](https://github.com/robot-assisted-projects/FRPL-RMA/issues/19) | Charlotte-Mecklenburg Schools | NC | 3702970 | NC-600 | — |
| [#20](https://github.com/robot-assisted-projects/FRPL-RMA/issues/20) | DALLAS ISD | TX | 4816230 | TX-057905 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#21](https://github.com/robot-assisted-projects/FRPL-RMA/issues/21) | Prince George's County Public Schools | MD | 2400510 | MD-16 | — |
| [#22](https://github.com/robot-assisted-projects/FRPL-RMA/issues/22) | DUVAL | FL | 1200480 | FL-16 | — |
| [#23](https://github.com/robot-assisted-projects/FRPL-RMA/issues/23) | Philadelphia City SD | PA | 4218990 | PA-126515001 | — |
| [#24](https://github.com/robot-assisted-projects/FRPL-RMA/issues/24) | CYPRESS-FAIRBANKS ISD | TX | 4816110 | TX-101907 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#25](https://github.com/robot-assisted-projects/FRPL-RMA/issues/25) | POLK | FL | 1201590 | FL-53 | — |
| [#26](https://github.com/robot-assisted-projects/FRPL-RMA/issues/26) | Memphis-Shelby County Schools | TN | 4700148 | TN-00792 | — |
| [#27](https://github.com/robot-assisted-projects/FRPL-RMA/issues/27) | Baltimore County Public Schools | MD | 2400120 | MD-03 | — |
| [#28](https://github.com/robot-assisted-projects/FRPL-RMA/issues/28) | Cobb County | GA | 1301290 | GA-633 | — |
| [#29](https://github.com/robot-assisted-projects/FRPL-RMA/issues/29) | LEE | FL | 1201080 | FL-36 | — |
| [#30](https://github.com/robot-assisted-projects/FRPL-RMA/issues/30) | NORTHSIDE ISD | TX | 4833120 | TX-015915 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#31](https://github.com/robot-assisted-projects/FRPL-RMA/issues/31) | KATY ISD | TX | 4825170 | TX-101914 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#32](https://github.com/robot-assisted-projects/FRPL-RMA/issues/32) | Jefferson County | KY | 2102990 | KY-056275000 | [#5](https://github.com/robot-assisted-projects/FRPL-RMA/issues/5) |
| [#33](https://github.com/robot-assisted-projects/FRPL-RMA/issues/33) | San Diego Unified | CA | 0634320 | CA-3768338 | — |
| [#34](https://github.com/robot-assisted-projects/FRPL-RMA/issues/34) | DeKalb County | GA | 1301740 | GA-644 | — |
| [#35](https://github.com/robot-assisted-projects/FRPL-RMA/issues/35) | School District No. 1 in the county of Denver and State of C | CO | 0803360 | CO-0880 | — |
| [#36](https://github.com/robot-assisted-projects/FRPL-RMA/issues/36) | Prince William County Public Schools | VA | 5103130 | VA-075 | — |
| [#37](https://github.com/robot-assisted-projects/FRPL-RMA/issues/37) | PINELLAS | FL | 1201560 | FL-52 | — |
| [#38](https://github.com/robot-assisted-projects/FRPL-RMA/issues/38) | Fulton County | GA | 1302280 | GA-660 | — |
| [#39](https://github.com/robot-assisted-projects/FRPL-RMA/issues/39) | Alpine District | UT | 4900030 | UT-01 | [#11](https://github.com/robot-assisted-projects/FRPL-RMA/issues/11) |
| [#40](https://github.com/robot-assisted-projects/FRPL-RMA/issues/40) | PASCO | FL | 1201530 | FL-51 | — |
| [#41](https://github.com/robot-assisted-projects/FRPL-RMA/issues/41) | Anne Arundel County Public Schools | MD | 2400060 | MD-02 | — |
| [#42](https://github.com/robot-assisted-projects/FRPL-RMA/issues/42) | Davidson County | TN | 4703180 | TN-00190 | — |
| [#43](https://github.com/robot-assisted-projects/FRPL-RMA/issues/43) | FORT BEND ISD | TX | 4819650 | TX-079907 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#44](https://github.com/robot-assisted-projects/FRPL-RMA/issues/44) | Greenville 01 | SC | 4502310 | SC-2301 | — |
| [#45](https://github.com/robot-assisted-projects/FRPL-RMA/issues/45) | Baltimore City Public Schools | MD | 2400090 | MD-30 | — |
| [#46](https://github.com/robot-assisted-projects/FRPL-RMA/issues/46) | OSCEOLA | FL | 1201470 | FL-49 | — |
| [#47](https://github.com/robot-assisted-projects/FRPL-RMA/issues/47) | ALBUQUERQUE | NM | 3500060 | NM-35001000 | — |
| [#48](https://github.com/robot-assisted-projects/FRPL-RMA/issues/48) | Jefferson County School District No. R-1 | CO | 0804800 | CO-1420 | — |
| [#49](https://github.com/robot-assisted-projects/FRPL-RMA/issues/49) | CONROE ISD | TX | 4815000 | TX-170902 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#50](https://github.com/robot-assisted-projects/FRPL-RMA/issues/50) | AUSTIN ISD | TX | 4808940 | TX-227901 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#51](https://github.com/robot-assisted-projects/FRPL-RMA/issues/51) | Davis District | UT | 4900210 | UT-07 | [#11](https://github.com/robot-assisted-projects/FRPL-RMA/issues/11) |
| [#52](https://github.com/robot-assisted-projects/FRPL-RMA/issues/52) | BREVARD | FL | 1200150 | FL-05 | — |
| [#53](https://github.com/robot-assisted-projects/FRPL-RMA/issues/53) | FORT WORTH ISD | TX | 4819700 | TX-220905 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#54](https://github.com/robot-assisted-projects/FRPL-RMA/issues/54) | Fresno Unified | CA | 0614550 | CA-1062166 | — |
| [#55](https://github.com/robot-assisted-projects/FRPL-RMA/issues/55) | Guilford County Schools | NC | 3701920 | NC-410 | — |
| [#56](https://github.com/robot-assisted-projects/FRPL-RMA/issues/56) | Milwaukee School District | WI | 5509600 | WI-3619 | — |
| [#57](https://github.com/robot-assisted-projects/FRPL-RMA/issues/57) | FRISCO ISD | TX | 4820010 | TX-043905 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#58](https://github.com/robot-assisted-projects/FRPL-RMA/issues/58) | Washoe County | NV | 3200480 | NV-16 | — |
| [#59](https://github.com/robot-assisted-projects/FRPL-RMA/issues/59) | Chesterfield County Public Schools | VA | 5100840 | VA-021 | — |
| [#60](https://github.com/robot-assisted-projects/FRPL-RMA/issues/60) | SEMINOLE | FL | 1201710 | FL-59 | — |
| [#61](https://github.com/robot-assisted-projects/FRPL-RMA/issues/61) | Elk Grove Unified | CA | 0612330 | CA-3467314 | — |
| [#62](https://github.com/robot-assisted-projects/FRPL-RMA/issues/62) | Long Beach Unified | CA | 0622500 | CA-1964725 | — |
| [#63](https://github.com/robot-assisted-projects/FRPL-RMA/issues/63) | VOLUSIA | FL | 1201920 | FL-64 | — |
| [#64](https://github.com/robot-assisted-projects/FRPL-RMA/issues/64) | Douglas County School District No. Re 1 | CO | 0803450 | CO-0900 | — |
| [#65](https://github.com/robot-assisted-projects/FRPL-RMA/issues/65) | Knox County | TN | 4702220 | TN-00470 | — |
| [#66](https://github.com/robot-assisted-projects/FRPL-RMA/issues/66) | Granite District | UT | 4900360 | UT-12 | [#11](https://github.com/robot-assisted-projects/FRPL-RMA/issues/11) |
| [#67](https://github.com/robot-assisted-projects/FRPL-RMA/issues/67) | Jordan District | UT | 4900420 | UT-14 | [#11](https://github.com/robot-assisted-projects/FRPL-RMA/issues/11) |
| [#68](https://github.com/robot-assisted-projects/FRPL-RMA/issues/68) | Howard County Public Schools | MD | 2400420 | MD-13 | — |
| [#69](https://github.com/robot-assisted-projects/FRPL-RMA/issues/69) | NORTH EAST ISD | TX | 4832940 | TX-015910 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#70](https://github.com/robot-assisted-projects/FRPL-RMA/issues/70) | ALDINE ISD | TX | 4807710 | TX-101902 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#71](https://github.com/robot-assisted-projects/FRPL-RMA/issues/71) | Forsyth County | GA | 1302220 | GA-658 | — |
| [#72](https://github.com/robot-assisted-projects/FRPL-RMA/issues/72) | MANATEE | FL | 1201230 | FL-41 | — |
| [#73](https://github.com/robot-assisted-projects/FRPL-RMA/issues/73) | ARLINGTON ISD | TX | 4808700 | TX-220901 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#74](https://github.com/robot-assisted-projects/FRPL-RMA/issues/74) | OMAHA PUBLIC SCHOOLS | NE | 3174820 | NE-280001000 | [#6](https://github.com/robot-assisted-projects/FRPL-RMA/issues/6) |
| [#75](https://github.com/robot-assisted-projects/FRPL-RMA/issues/75) | KLEIN ISD | TX | 4825740 | TX-101915 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#76](https://github.com/robot-assisted-projects/FRPL-RMA/issues/76) | Winston Salem / Forsyth County Schools | NC | 3701500 | NC-340 | — |
| [#77](https://github.com/robot-assisted-projects/FRPL-RMA/issues/77) | ST. JOHNS | FL | 1201740 | FL-55 | — |
| [#78](https://github.com/robot-assisted-projects/FRPL-RMA/issues/78) | Rutherford County | TN | 4703690 | TN-00750 | — |
| [#79](https://github.com/robot-assisted-projects/FRPL-RMA/issues/79) | Cherry Creek School District No. 5 in the county of Arapah | CO | 0802910 | CO-0130 | — |
| [#80](https://github.com/robot-assisted-projects/FRPL-RMA/issues/80) | Clayton County | GA | 1301230 | GA-631 | — |
| [#81](https://github.com/robot-assisted-projects/FRPL-RMA/issues/81) | GARLAND ISD | TX | 4820340 | TX-057909 | [#16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) |
| [#82](https://github.com/robot-assisted-projects/FRPL-RMA/issues/82) | Henrico County Public Schools | VA | 5101890 | VA-043 | — |
| [#83](https://github.com/robot-assisted-projects/FRPL-RMA/issues/83) | Charleston 01 | SC | 4501440 | SC-1001 | — |
| [#84](https://github.com/robot-assisted-projects/FRPL-RMA/issues/84) | Seattle School District No. 1 | WA | 5307710 | WA-17001 | — |
