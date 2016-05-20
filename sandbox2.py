def get_args(self,cmd):
  """return the cmd_name and args in a tuple, accounting for quotes"""

  args = cmd.split(' ')
  name = args[0]
  args = ' '.join(args[1:]).strip()

  if args:
    l = []
    quote = False
    s = ''
    for c in args:
      if c==' ':
        if quote:
          s += c
        elif s:
          l.append(s)
          s = ''
      elif c=='"':
        if quote:
          quote = False
        else:
          quote = True
      else:
        s += c
    if s:
      l.append(s)
  else:
    l = []

  return (name,l)

print get_args(None,'echo testing hello')
print get_args(None,'echo  testing   hello')
print get_args(None,'echo "testing hello"')
print get_args(None,'echo  "testing   hello"')
print get_args(None,'echo "testing hello " "nope" "yep tep"tacos ')
print get_args(None,'echo')
