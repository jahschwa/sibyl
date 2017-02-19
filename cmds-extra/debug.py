from sibyl.lib.decorators import botcmd

import logging
log = logging.getLogger(__name__)

@botcmd(name='exec',ctrl=True,hidden=True)
def _exec(bot,mess,args):
  exec ' '.join(args)

@botcmd(name='eval',ctrl=True,hidden=True)
def _eval(bot,mess,args):
  return unicode(eval(' '.join(args)))
