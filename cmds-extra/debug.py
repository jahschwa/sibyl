# WARNING: USE AT YOUR OWN RISK
#
# These commands implicitly allow for arbitrary code execution.
#
# They are only recommended for use on local testing instances.
#
# If you really want to have them on an internet-facing Sibyl, then at least
# restrict them in bw_list in your config.
#
# The Sibyl project and its developers are not responsible for anything that
# happens due to the use of these commands.

from sibyl.lib.decorators import botcmd

import logging
log = logging.getLogger(__name__)

@botcmd(name='exec',ctrl=True,hidden=True,raw=True)
def _exec(bot,mess,args):
  exec args

@botcmd(name='eval',ctrl=True,hidden=True,raw=True)
def _eval(bot,mess,args):
  return unicode(eval(args))
