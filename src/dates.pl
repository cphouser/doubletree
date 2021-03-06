#!/usr/bin/env swipl

:- rdf_create_graph('temp').

xcat_print_year(LDateTime, Print):-
    rdf(LDateTime, xcat:year, Year),
    Year = YearInt^^_,
    format(atom(Print), '~d', YearInt).

xcat_print_month(LDateTime, Print, Sort) :-
    rdf(LDateTime, xcat:month, Month),
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
        (   MonthInt = 12, Print = "Dec")),
    format(atom(Sort), '~`0t~d~2+', MonthInt).

xcat_print_day(LDateTime, Print) :-
    rdf(LDateTime, xcat:day, Day),
    Day = DayInt^^_, %Why Doesn't xsd:gDay work?
    xcat_print_month(LDateTime, LeadStr, _),
    xcat_print_year(LDateTime, Year),
    format(atom(Print), '~s ~`0t~d~2+ ~s', [LeadStr, DayInt, Year]).

xcat_print_hour(LDateTime, Print) :-
    rdf(LDateTime, xcat:hour, Hour),
    Hour = HourInt^^_,
    xcat_print_day(LDateTime, LeadStr),
    format(atom(Print), '~s ~`0t~d~2+', [LeadStr, HourInt]).

xcat_print_minute(LDateTime, Print) :-
    rdf(LDateTime, xcat:minute, Minute),
    Minute = MinuteInt^^_,
    xcat_print_hour(LDateTime, LeadStr),
    format(atom(Print), '~s:~`0t~d~2+', [LeadStr, MinuteInt]).

xcat_print_second(LDateTime, Print) :-
    rdf(LDateTime, xcat:second, Second),
    Second = SecondInt^^_,
    xcat_print_minute(LDateTime, LeadStr),
    format(atom(Print), '~s:`0t~d~2+', [LeadStr, SecondInt]).

xcat_print_microsec(LDateTime, Print) :-
    rdf(LDateTime, xcat:microsecond, Microsec),
    Microsec = MicrosecInt^^_,
    xcat_print_second(LDateTime, LeadStr),
    format(atom(Print), '~s.~|~`0t~d~6+', [LeadStr, MicrosecInt]).

xcat_print_date(LDateTime, PrintStr) :-
    xcat_print_microsec(LDateTime, PrintStr), !;
    xcat_print_second(LDateTime, PrintStr), !;
    xcat_print_minute(LDateTime, PrintStr), !;
    xcat_print_hour(LDateTime, PrintStr), !;
    xcat_print_day(LDateTime, PrintStr), !;
    (   xcat_print_month(LDateTime, MonthStr, _),
        xcat_print_year(LDateTime, YearStr),
        format(atom(PrintStr), '~s ~s', [MonthStr, YearStr])
        ), !;
    xcat_print_year(LDateTime, PrintStr).

% would these be faster if I put the recursive bit at the end?
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

xcat_within(LDateTime, OtherDT) :-
    xcat_same_minute(LDateTime, OtherDT), !;
    xcat_same_hour(LDateTime, OtherDT), !;
    xcat_same_day(LDateTime, OtherDT), !;
    xcat_same_month(LDateTime, OtherDT), !;
    xcat_same_year(LDateTime, OtherDT).

% return the a ldatetime of just the year
xcat_year(LDateTime, LDT_Year) :-
    (   xcat_same_year(LDateTime, LDT_Year),
        \+ rdf(LDT_Year, xcat:month, _), !);
    xcat_blank_year(LDateTime, LDT_Year).

xcat_month(LDateTime, LDT_Month) :-
    (   xcat_same_month(LDateTime, LDT_Month),
        \+ rdf(LDT_Month, xcat:day, _), !);
    xcat_blank_month(LDateTime, LDT_Month).

xcat_day(LDateTime, LDT_Day) :-
    (   xcat_same_day(LDateTime, LDT_Day),
        \+ rdf(LDT_Day, xcat:hour, _), !);
    xcat_blank_day(LDateTime, LDT_Day).

xcat_hour(LDateTime, LDT_Hour) :-
    (   xcat_same_hour(LDateTime, LDT_Hour),
        \+ rdf(LDT_Hour, xcat:minute, _), !);
    xcat_blank_hour(LDateTime, LDT_Hour).

xcat_minute(LDateTime, LDT_Minute) :-
    (   xcat_same_minute(LDateTime, LDT_Minute),
        \+ rdf(LDT_Minute, xcat:second, _), !);
    xcat_blank_minute(LDateTime, LDT_Minute).

xcat_blank_year(LDateTime, LDT_Year) :-
    rdf(LDateTime, xcat:year, Year),
    rdf_create_bnode(LDT_Year),
    rdf_assert(LDT_Year, rdf:type, xcat:'LDateTime', 'temp'),
    rdf_assert(LDT_Year, xcat:year, Year, 'temp').

xcat_blank_month(LDateTime, LDT_Month) :-
    rdf(LDateTime, xcat:month, Month),
    xcat_blank_year(LDateTime, LDT_Month),
    rdf_assert(LDT_Month, xcat:month, Month, 'temp').

xcat_blank_day(LDateTime, LDT_Day) :-
    rdf(LDateTime, xcat:day, Day),
    xcat_blank_month(LDateTime, LDT_Day),
    rdf_assert(LDT_Day, xcat:day, Day, 'temp').

xcat_blank_hour(LDateTime, LDT_Hour) :-
    rdf(LDateTime, xcat:hour, Hour),
    xcat_blank_day(LDateTime, LDT_Hour),
    rdf_assert(LDT_Hour, xcat:hour, Hour, 'temp').

xcat_blank_minute(LDateTime, LDT_Minute) :-
    rdf(LDateTime, xcat:minute, Minute),
    xcat_blank_month(LDateTime, LDT_Minute),
    rdf_assert(LDT_Minute, xcat:minute, Minute, 'temp').
