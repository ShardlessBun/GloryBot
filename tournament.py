from typing import Union, List, Optional, Dict, Tuple, Set, FrozenSet

import random

from dis_snek import Snake
from dis_snek.models import Member, GuildChannel, User, Scale, slash_command, slash_option, OptionTypes, \
    InteractionContext, check, AutocompleteContext


class Tournament(object):
    owners: List[Member]
    players: List[str]
    rounds: List[List[FrozenSet[str]]]

    def __init__(self, creator: Member):
        self.owners = [creator]
        self.players = []
        self.rounds = []

    def add(self, name: str):
        if name in self.players:
            raise ValueError
        self.players.append(name)

    def remove(self, name: str):
        self.players.remove(name)  # Throws a ValueError if the name doesn't exist

    def _generate_round(self) -> List[FrozenSet[str]]:
        new_round = []
        active_players = self.players.copy()
        random.shuffle(active_players)

        while len(active_players) > 1:
            pair = frozenset({active_players.pop(), active_players.pop()})
            new_round.append(pair)
        if len(active_players) == 1:  # This means we have an odd # of players and need a bye
            new_round.append(frozenset({"bye", active_players.pop()}))

        return new_round

    def _evaluate_round(self, potential_round: List[FrozenSet[str]]) -> int:
        matchup_scores = dict()
        for i, previous_round in enumerate(self.rounds):
            for pair in previous_round:
                if pair not in matchup_scores:
                    matchup_scores[pair] = i + 1
                else:
                    matchup_scores[pair] *= i + 1  # We want to heavily penalize recent matchups

        score = 0
        for pair in potential_round:
            if pair in matchup_scores:
                score += matchup_scores[pair]

        print(f"Total score for round {potential_round} is {score}")
        return score

    def next_round(self) -> List[FrozenSet[str]]:
        if len(self.rounds) == 0:
            new_round = self._generate_round()
        else:
            potential_rounds = []
            for _ in range(100):
                r = self._generate_round()
                potential_rounds.append((r, self._evaluate_round(r)))

            potential_rounds.sort(key=lambda x: x[1])  # Sort by lowest (best) scores
            new_round = potential_rounds[0][0]

        self.rounds.append(new_round)
        return new_round


class TournamentScale(Scale):
    active_tournaments: List[Tuple[Tournament, GuildChannel]]

    def __init__(self, client: Snake):
        self.client = client
        self.active_tournaments = []

    async def valid_tournaments_check(self, ctx: InteractionContext) -> bool:
        if len(self.active_tournaments) == 0:
            await ctx.send(f"Error: There are no active tournaments")
            return False
        tournament = next(filter(lambda t: t[1] == ctx.channel, self.active_tournaments), None)
        if not tournament:
            await ctx.send(f"Error: There is no active tournament in this channel")
            return False
        return True

    @slash_command(
        name="tournament",
        description="Keep track of a Glorybound tournament through the bot",
        sub_cmd_name="create",
        sub_cmd_description="Create a new Glorybound tournament in this channel",
    )
    async def tournament(self, ctx: InteractionContext):
        tournament = next(filter(lambda t: t[1] == ctx.channel, self.active_tournaments), None)
        if tournament:
            await ctx.send(f"Error: There is already an active tournament in this channel")
            return
        self.active_tournaments.append((Tournament(ctx.author), ctx.channel))
        await ctx.send(f"New tournament created by {ctx.author.mention}")

    @tournament.subcommand(sub_cmd_name="add",
                           sub_cmd_description="Add a player to the tournament")
    @slash_option(name="player_name",
                  opt_type=OptionTypes.STRING,
                  description="Player name to add",
                  required=True)
    async def tournament_add(self, ctx: InteractionContext, player_name: str):
        """
        Adds a player to the tournament (by name)

        :param ctx: The invoked InteractionContext
        :param player_name: Name of the player to be added (as a string)
        :sends: A message confirming that the player has been added
        """
        if len(self.active_tournaments) == 0:
            await ctx.send(f"Error: There are no active tournaments")
            return
        tournament = next(filter(lambda t: t[1] == ctx.channel, self.active_tournaments), None)
        if not tournament:
            await ctx.send(f"Error: There is no active tournament in this channel")
            return

        tournament_obj: Tournament = tournament[0]
        try:
            tournament_obj.add(player_name)
            await ctx.send(f"{player_name} added to the tournament!")
        except ValueError:
            await ctx.send(f"Error: {player_name} is already in the tournament")

    @tournament.subcommand(sub_cmd_name="remove",
                           sub_cmd_description="Removes a player from the tournament")
    @slash_option(name="player_name",
                  opt_type=OptionTypes.STRING,
                  description="Player name to remove",
                  required=True)
    async def tournament_remove(self, ctx: InteractionContext, player_name: str):
        """
        Removes a player from the tournament (by name)

        :param ctx: The invoked InteractionContext
        :param player_name: Name of the player to be removed (as a string)
        :sends: A message confirming that the player has been removed,
                or an error message stating that the player is not part of the tournament.
        """
        if len(self.active_tournaments) == 0:
            await ctx.send(f"Error: There are no active tournaments")
            return
        tournament = next(filter(lambda t: t[1] == ctx.channel, self.active_tournaments), None)
        if not tournament:
            await ctx.send(f"Error: There is no active tournament in this channel")
            return

        tournament_obj: Tournament = tournament[0]
        try:
            tournament_obj.remove(player_name)
            await ctx.send(f"{player_name} removed from the tournament")
        except ValueError:
            await ctx.send(f"Error: {player_name} is not in the tournament")

    @tournament_remove.autocomplete("player_name")
    async def autocomplete_players(self, ctx: AutocompleteContext, player_name: str):
        tournament = next(filter(lambda t: t[1] == ctx.channel, self.active_tournaments), None)
        print(tournament)
        if tournament:
            players = [{'name': p, 'value': p} for p in tournament[0].players]
            print(players)
            await ctx.send(choices=players)
        else:
            return ctx.send(choices=[])

    @tournament.subcommand(sub_cmd_name="next_round",
                           sub_cmd_description="Starts the next round of the tournament")
    async def tournament_next_round(self, ctx: InteractionContext):
        if len(self.active_tournaments) == 0:
            await ctx.send(f"Error: There are no active tournaments")
            return
        tournament = next(filter(lambda t: t[1] == ctx.channel, self.active_tournaments), None)
        if not tournament:
            await ctx.send(f"Error: There is no active tournament in this channel")
            return

        tournament_obj: Tournament = tournament[0]

        new_round = tournament_obj.next_round()
        message_txt = f"Round {len(tournament_obj.rounds)} pairings:"
        for pair in new_round:
            p = list(pair)
            if 'bye' not in p:
                message_txt += f"\n**{p[0]}** vs **{p[1]}**"
            else:
                message_txt += f"\n**{[x for x in p if x != 'bye'][0]}** gets the bye"

        await ctx.send(message_txt)


def setup(snek):
    TournamentScale(snek)
