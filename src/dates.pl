#!/usr/bin/env swipl

xcat_print_month(Month, Print, Sort) :-
    Month = MonthInt^^_, %Why Doesn't xsd:gMonth work?
    (   (   MonthInt = 1, Print = "Jan");
        (   MonthInt = 2, Print = "Feb");
        (   MonthInt = 3, Print = "Mar");
        (   MonthInt = 4, Print = "Apr");
        (   MonthInt = 5, Print = "May");
        (   MonthInt = 6, Print = "Jun");
        (   MonthInt = 7, Print = "Jul");
        (   MonthInt = 8, Print = "Aug");
        (   MonthInt = 9, Print = "Sep");
        (   MonthInt = 10, Print = "Oct");
        (   MonthInt = 11, Print = "Nov");
        (   MonthInt = 12, Print = "Dec")
    ),
    format(atom(Sort), '~`0t~d~2+', MonthInt).

xcat_print_day(Day, Print) :-
    Day = DayInt^^_, %Why Doesn't xsd:gDay work?
    format(atom(Print), '~`0t~d~2+', DayInt).


xcat_same_year(LDateTime, OtherDT) :-
    rdf(LDateTime, xcat:year, Year^^xsd:gYear),
    rdf(OtherDT, xcat:year, Year^^xsd:gYear).

xcat_same_month(LDateTime, OtherDT) :-
    xcat_same_year(LDateTime, OtherDT),
    rdf(LDateTime, xcat:month, Month^^xsd:gMonth),
    rdf(OtherDT, xcat:month, Month^^xsd:gMonth).

xcat_same_day(LDateTime, OtherDT) :-
    xcat_same_month(LDateTime, OtherDT),
    rdf(LDateTime, xcat:day, Day^^xsd:gDay),
    rdf(OtherDT, xcat:day, Day^^xsd:gDay).

xcat_same_hour(LDateTime, OtherDT) :-
    xcat_same_day(LDateTime, OtherDT),
    rdf(LDateTime, xcat:hour, Hour^^xsd:nonNegativeInteger),
    rdf(OtherDT, xcat:hour, Hour^^xsd:nonNegativeInteger).

xcat_same_minute(LDateTime, OtherDT) :-
    xcat_same_hour(LDateTime, OtherDT),
    rdf(LDateTime, xcat:minute, Minute^^xsd:nonNegativeInteger),
    rdf(OtherDT, xcat:minute, Minute^^xsd:nonNegativeInteger).
