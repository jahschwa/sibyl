import random
from sibyl.lib.protocol import Message
from sibyl.lib.decorators import botinit, botcmd
import sibyl_games

@botinit 
def init(bot):
    bot.add_var('Game', None)
    
@botcmd
def game(bot, mess, args):
    """
    A module for playing games.
    
    Arguments:
        0: Name of the game to be played
    """
    # Initialization of Game object
    if bot.Game is not None:
        return 'Game of ' + bot.Game.game + ' already in progress.'

    games = {'battleship': {'alias': ['battleship'],
                            'class': sibyl_games.Battleship(bot, mess)}}

    for name in games:
       if args[0] in games[name]['alias']:
            bot.Game = games[name]['class']
            break
    
    if not bot.Game:
        return 'Game not in library.'
    
    return 'Starting game of ' + bot.Game.game + \
           '! Please register with "sibyl register". ' \
           'Unregister with "sibyl unregister".'
    
@botcmd
def register(bot, mess, args):
    """
    Register user for playing Game.
    """
    if bot.Game is not None:
        if not bot.Game.started:
            if bot.Game.num_players == bot.Game.max_players:
                return 'Maximum of ' + str(len(bot.Game.players)) + \
                       ' already registered.'

            player = mess.get_user()
            bot.Game.players[player.get_name()] = {
                    'user': player,
                    'nick': player.get_name()}
            bot.Game.num_players += 1
            return player.get_name() + ' has been successfully registered.  ' \
                   'Current number of players: ' + str(bot.Game.num_players)
        else:
            return 'Game has already started. Registrations are locked.'
    else:
        return 'There is no current active game.'

@botcmd
def unregister(bot, mess, args):
    """
    Unregister user from Game.
    """
    if bot.Game is not None:
        if not bot.Game.started:
            nick = mess.get_user().get_name()
            if nick in bot.Game.players:
                del bot.Game.players[nick]
                Game.num_players -= 1
                return nick + ' has been successfully unregistered. ' \
                       'Current number of players: ' + str(bot.Game.num_players)
            else:
                return nick + ' is not currently registered.'
        else:
            return 'Game has already started. Registrations are locked.'
    else:
        return 'There is no current active game.'
        
@botcmd
def startgame(bot, mess, args):
    """
    Start a Game.
    """
    if bot.Game is not None:
        if not bot.Game.started:
            if bot.Game.min_players <= bot.Game.num_players <= \
                    bot.Game.max_players:
                bot.reply('Game of ' + bot.Game.game + ' started!', mess)
                bot.Game.started = True
                bot.Game.start_game()
            elif bot.Game.num_players < bot.Game.min_players:
                return 'Not enough players to start game of ' + \
                       bot.Game.game + '.'
            else:
                return 'Too many players to start game of ' + \
                       bot.Game.game + '.'
        else:
            return 'Game of ' + bot.Game.game + ' has already started!'
    else:
        return 'There is no current active game.'

@botcmd
def move(bot, mess, args):
    """
    Make a move in a Game.

    Arguments:
        0: The move to be made
    """
    if bot.Game is not None:
        if bot.Game.pm_only:
            if mess.get_room() is not None:
                return bot.Game.game + \
                       ' is played only through private messages.'

        if mess.get_user().get_name() not in bot.Game.players:
            return 'You are not a player in the current game.'

        if bot.Game.lock:
            if mess.get_user() is not bot.Game.current_player:
                return 'It is not your turn. Current player: ' + \
                       str(bot.Game.current_player)

        return bot.Game.move(mess.get_user().get_name(), args)
    else:
        return 'There is no current active game.'

@botcmd
def quitgame(bot, mess, args):
    """
    Quit the current Game.
    """
    if bot.Game is not None:
        if not bot.Game.quit_confirm:
            bot.Game.quit_confirm = True
            return 'Quit game of ' + bot.Game.game + \
                   '? Repeat "sibyl quitgame" to confirm.'
        del bot.Game
        bot.add_var('Game', None)
        return 'Game quit successfully.'
    else:
        return 'There is no current active game.'