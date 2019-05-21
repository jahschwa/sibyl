import random

class Battleship(object):
    """
    Game object for Battleship.
    """
    def __init__ (self, bot, mess):
        self.bot = bot
        self.room = mess.get_room()
        self.game = 'Battleship'
        self.min_players = 2
        self.max_players = 2
        self.num_players = 0
        self.players = {}
        self.turn_order = []
        self.started = False
        self.pm_only = True
        self.current_player = None
        self.quit_confirm = False
        self.phase = None
        self.turn = 2  # Set for integer division
        self.lock = False  # Toggle to True when only one player may move
        self.SHIPS = ['carrier', 'battleship', 'destroyer',
                      'submarine', 'patrol']
        self.RANKS = 'abcdefghjk'
        self.FILES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    def start_game(self):
        self.phase = 'placement'

        self.turn_order = list(self.players.keys())
        random.shuffle(self.turn_order)
        self.current_player = self.turn_order[self.turn % 2]
        for p in self.players:
            self.players[p]['id'] = '2'
        self.players[self.current_player]['id'] = '1'

        for player in self.players:
            self.players[player]['to place'] = self.SHIPS[:]
            self.players[player]['ships'] = {'carrier': [],
                                             'battleship': [],
                                             'destroyer': [],
                                             'submarine': [],
                                             'patrol': []}
            self.players[player]['sunk'] = []
            self.players[player]['ready'] = False
            self.players[player]['hits'] = []
            self.players[player]['misses'] = []
            self.players[player]['x'] = []
            self.players[player]['o'] = []
            self.display_board(player, placement=True)
            self.bot.send('Please place your ships with "sibyl move '
                          '[ship name] [bow location] [cardinal '
                          'direction]."', self.players[player]['user'])
            self.bot.send('Remaining ships to be placed: ' +
                          ', '.join(self.players[player]['to place']),
                          self.players[player]['user'])

    def move(self, player, move):
        if self.phase == 'placement':
            if not self.players[player]['ready']:
                if move[0] == 'confirm':
                    self.confirm(player)
                else:
                    return self.place(player, move)
            else:
                return 'Your fleet has already been deployed!'
        elif self.phase == 'battle':
            if len(move) != 1:
                return 'Invalid move format. Please use "sibyl move [target coordinates]" to attack.'
            move = move[0].lower()
            if move in self.players[player]['hits'] or \
                move in self.players[player]['misses']:
                return 'You have already hit that target! Choose a different ' \
                       'target.'

            return self.fire(player, move)

    def place(self, player, move):
        # move: [ship name] [bow location] [cardinal direction]
        if len(move) != 3:
            return 'Invalid move format. Please use "sibyl move [ship name] [bow location] [cardinal direction]'
            
        ship, bow, direction = [m.lower() for m in move]

        # Check for legal values
        if ship not in self.SHIPS:
            return 'Invalid ship name. Choose from ' + ', '.join(self.SHIPS)

        if bow[0] not in self.RANKS or int(bow[1:]) not in self.FILES:
            return 'Invalid ship location. Note: "I" is an invalid file.'

        if direction not in 'nsew':
            return 'Invalid ship direction. Choose N, S, E, or W.'

        # Check that ship placement remains on the board
        if ship == 'carrier':
            if (bow[0] < 'e' and direction == 'w') or \
                (bow[0] > 'f' and direction == 'e') or \
                (bow[1:] < '5' and direction == 'n') or \
                (bow[1:] > '6' and direction == 's'):
                return 'Invalid ship direction. Ships must stay on the board.'

            if direction == 'n' or direction == 's':
                idx = self.FILES.index(int(bow[1:]))
                if direction == 'n':
                    nodes = [bow[0] + str(f) for f in self.FILES[idx-4:idx+1]]
                else:
                    nodes = [bow[0] + str(f) for f in self.FILES[idx:idx+5]]
            else:
                idx = self.RANKS.index(bow[0])
                if direction == 'e':
                    nodes = [r + bow[1:] for r in self.RANKS[idx:idx+5]]
                else:
                    nodes = [r + bow[1:] for r in self.RANKS[idx-4:idx+1]]
        elif ship == 'battleship':
            if (bow[0] < 'd' and direction == 'w') or \
                (bow[0] > 'g' and direction == 'e') or \
                (bow[1:] < '4' and direction == 'n') or \
                (bow[1:] > '7' and direction == 's'):
                return 'Invalid ship direction. Ships must stay on the board.'

            if direction == 'n' or direction == 's':
                idx = self.FILES.index(int(bow[1:]))
                if direction == 'n':
                    nodes = [bow[0] + str(f) for f in self.FILES[idx-3:idx+1]]
                else:
                    nodes = [bow[0] + str(f) for f in self.FILES[idx:idx+4]]
            else:
                idx = self.RANKS.index(bow[0])
                if direction == 'e':
                    nodes = [r + bow[1:] for r in self.RANKS[idx:idx+4]]
                else:
                    nodes = [r + bow[1:] for r in self.RANKS[idx-3:idx+1]]
        elif ship == 'destroyer' or ship == 'submarine':
            if (bow[0] < 'c' and direction == 'w') or \
                (bow[0] > 'h' and direction == 'e') or \
                (bow[1:] < '3' and direction == 'n') or \
                (bow[1:] > '8' and direction == 's'):
                return 'Invalid ship direction. Ships must stay on the board.'

            if direction == 'n' or direction == 's':
                idx = self.FILES.index(int(bow[1:]))
                if direction == 'n':
                    nodes = [bow[0] + str(f) for f in self.FILES[idx-2:idx+1]]
                else:
                    nodes = [bow[0] + str(f) for f in self.FILES[idx:idx+3]]
            else:
                idx = self.RANKS.index(bow[0])
                if direction == 'e':
                    nodes = [r + bow[1:] for r in self.RANKS[idx:idx+3]]
                else:
                    nodes = [r + bow[1:] for r in self.RANKS[idx-2:idx+1]]
        elif ship == 'patrol':
            if (bow[0] < 'c' and direction == 'w') or \
                (bow[0] > 'j' and direction == 'e') or \
                (bow[1:] < '2' and direction == 'n') or \
                (bow[1:] > '9' and direction == 's'):
                return 'Invalid ship direction. Ships must stay on the board.'

            if direction == 'n' or direction == 's':
                idx = self.FILES.index(int(bow[1:]))
                if direction == 'n':
                    nodes = [bow[0] + str(f) for f in self.FILES[idx-1:idx+1]]
                else:
                    nodes = [bow[0] + str(f) for f in self.FILES[idx:idx+2]]
            else:
                idx = self.RANKS.index(bow[0])
                if direction == 'e':
                    nodes = [r + bow[1:] for r in self.RANKS[idx:idx+2]]
                else:
                    nodes = [r + bow[1:] for r in self.RANKS[idx-1:idx+1]]

        # Check for intersection. Note that a ship cannot intersect with itself
        list_of_nodes = [self.players[player]['ships'][s] for s in self.SHIPS
                         if s != ship]
        occupied = [node for s in list_of_nodes for node in s]
        if any(n in occupied for n in nodes):
            return 'Invalid ship location. Ships cannot intersect.'

        # Place ship on board
        self.players[player]['ships'][ship] = nodes
        if ship in self.players[player]['to place']:
            self.players[player]['to place'].remove(ship)
        self.bot.send('Successfully placed ' + ship + '.',
                      self.players[player]['user'])
        self.display_board(player, placement=True)

        # Prompt further placement
        if self.players[player]['to place']:
            return 'Remaining ships to be placed: ' + \
                   ', '.join(self.players[player]['to place'])
        else:
            return 'All ships have been placed. Confirm with ' \
                   '"sibyl move confirm" or use "sibyl move [ship name] ' \
                   '[bow location] [cardinal direction]" to replace.'

    def confirm(self, player):
        del self.players[player]['to place']
        list_of_nodes = [self.players[player]['ships'][s] for s in self.SHIPS]
        self.players[player]['nodes'] = [node for ship in list_of_nodes for
                                         node in ship]
        self.bot.send('Fleet deployed. Waiting for other player.',
                      self.players[player]['user'])
        self.players[player]['ready'] = True

        if all([self.players[p]['ready'] for p in self.players]):
            for player in self.players:
                self.bot.send('Both players'' fleets have been deployed. '
                              'Battle start!',
                              self.players[player]['user'])
                self.bot.send(self.current_player + ' goes first.',
                              self.players[player]['user'])
                self.display_board(player)
            self.phase = 'battle'
            self.lock = True
            self.bot.send('Please choose a target with '
                          '"sibyl move [target coordinates]".',
                          self.players[self.current_player]['user'])

    def fire(self, player, move):
        if move[0] not in self.RANKS or int(move[1:]) not in self.FILES:
            return 'Invalid target location. Choose a target on the board.'

        target = self.turn_order[(self.turn + 1) % 2]
        if move in self.players[target]['nodes']:
            self.players[player]['hits'].append(move)
            self.players[target]['x'].append(move)
            self.bot.send('Target hit!', self.players[player]['user'])
            self.check_if_sunk(target, move)
        else:
            self.players[player]['misses'].append(move)
            self.players[target]['o'].append(move)
            self.bot.send('Target missed.', self.players[player]['user'])

        self.display_board(player)

        if self.phase is not 'gameover':
            self.turn += 1
            self.current_player = self.turn_order[self.turn % 2]
            self.display_board(target)
            self.bot.send('Please choose a target with '
                          '"sibyl move [target location]".',
                          self.players[self.current_player]['user'])
        else:
            self.quit_game(target, player)

    def check_if_sunk(self, target, move):
        for ship in self.SHIPS:
            if move in self.players[target]['ships'][ship]:
                self.players[target]['ships'][ship].remove(move)

            if not self.players[target]['ships'][ship]:
                if ship not in self.players[target]['sunk']:
                    for player in self.players:
                        self.bot.send(self.players[target]['nick'] +
                                      "'s " + ship + ' has been sunk!',
                                      self.players[player]['user'])
                                      
                    self.check_if_game_over(target)
                    self.players[target]['sunk'].append(ship)

    def check_if_game_over(self, target):
        for ship in self.SHIPS:
            if self.players[target]['ships'][ship]:
                return

        self.phase = 'gameover'

    def quit_game(self, target, player):
        self.quit_confirm = True
        if self.room is not None:
            self.bot.send('All of ' + self.players[target]['nick'] + "'s ships "
                          "have been sunk!", self.room)
            self.bot.send(self.players[player]['nick'] + ' is the winner!',
                          self.room)
            self.bot.send('Game completed. Use "sibyl quitgame" to shut down.',
                          self.room)
        else:
            for player_ in self.players:
                self.bot.send('All of ' + self.players[target]['nick'] + "'s ships "
                          "have been sunk!", self.players[player_]['user'])
                self.bot.send(self.players[player]['nick'] + ' is the winner!',
                          self.players[player_]['user'])
                self.bot.send('Game completed. Use "sibyl quitgame" to shut down.',
                          self.players[player_]['user'])
            
    def display_board(self, player, placement=False):
        if placement:
            board = 'Ship Placement'
        else:
            board = 'Turn ' + str(self.turn // 2) + \
                    ' | Player ' + self.players[self.current_player]['id']
            board = ' \n '.join([board,
                                 '    A   B   C   D   E   F   G   H   J   K'])

            for file in range(1, 11):
                f = str(file)
                hits = [h[0] for h in self.players[player]['hits']
                        if h[1:] == f]
                misses = [m[0] for m in self.players[player]['misses']
                          if m[1:] == f]
                row = [f]
                if file < 10:
                    for rank in self.RANKS:
                        if rank in hits:
                            row.append('X')
                        elif rank in misses:
                            row.append('O')
                        else:
                            row.append('.')
                    board = ' \n '.join([board, '   '.join(row)])
                else:
                    for rank in self.RANKS:
                        if rank in hits:
                            row.append('X ')
                        elif rank in misses:
                            row.append('O ')
                        else:
                            row.append('. ')
                    board = ' \n '.join([board, '  '.join(row)])
            board = ' \n '.join([board,
                                 '    -------------------------------------'])
        board = ' \n '.join([board, '    A   B   C   D   E   F   G   H   J   K'])

        for file in range(1, 11):
            f = str(file)
            hits = [h[0] for h in self.players[player]['x']
                    if h[1:] == f]
            misses = [m[0] for m in self.players[player]['o']
                      if m[1:] == f]
            carrier = [c[0] for c in self.players[player]['ships']['carrier']
                       if c[1:] == f]
            bship = [b[0] for b in self.players[player]['ships']['battleship']
                     if b[1:] == f]
            destroy = [d[0] for d in self.players[player]['ships']['destroyer']
                       if d[1:] == f]
            sub = [s[0] for s in self.players[player]['ships']['submarine']
                   if s[1:] == f]
            patrol = [p[0] for p in self.players[player]['ships']['patrol']
                      if p[1:] == f]
            row = [f]
            
            if file < 10:
                for rank in self.RANKS:
                    if rank in hits:
                        row.append('X')
                    elif rank in misses:
                        row.append('O')
                    elif rank in carrier:
                        row.append('C')
                    elif rank in bship:
                        row.append('B')
                    elif rank in destroy:
                        row.append('D')
                    elif rank in sub:
                        row.append('S')
                    elif rank in patrol:
                        row.append('P')
                    else:
                        row.append('.')
                board = ' \n '.join([board, '   '.join(row)])
            else:
                for rank in self.RANKS:
                    if rank in hits:
                        row.append('X ')
                    elif rank in misses:
                        row.append('O ')
                    elif rank in carrier:
                        row.append('C ')
                    elif rank in bship:
                        row.append('B ')
                    elif rank in destroy:
                        row.append('D ')
                    elif rank in sub:
                        row.append('S ')
                    elif rank in patrol:
                        row.append('P ')
                    else:
                        row.append('. ')
                board = ' \n '.join([board, '  '.join(row)])

        self.bot.send(board, self.players[player]['user'])
