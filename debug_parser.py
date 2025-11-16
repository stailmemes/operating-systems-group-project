import argparser, process_subsystem
jobctl = process_subsystem.JobControl(print_fn=print)
p = argparser.build_parser(jobctl)
args = p.parse_args(['echo','hello'])
print('func repr:', args.func)
print('type:', type(args.func))
print('isinstance str:', isinstance(args.func,str))
print('callable:', callable(args.func))
try:
    args.func(args)
    print('call succeeded')
except Exception as e:
    print('call raised', e)

args2 = p.parse_args(['jobs'])
print('jobs func repr', args2.func, type(args2.func), isinstance(args2.func,str), callable(args2.func))
try:
    args2.func(args2)
    print('jobs call succeeded')
except Exception as e:
    print('jobs call raised', e)
