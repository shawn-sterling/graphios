from graphios import process_nagios_perf_data
import pytest


#	 
def test_process_perf_string():
    lines = process_nagios_perf_data('', "'_var'=9GB;15;15;0;15 '_foo.bar'=2GB;4;4;0;4 '_bar baz'=4GB;4;4;0;4", '123')

    assert 3 == len(lines)

    assert "'_var' 9 123" == lines[0]
    assert "'_foo_bar' 2 123" == lines[1]
    assert "'_bar_baz' 4 123" == lines[2]
