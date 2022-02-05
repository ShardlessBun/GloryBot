import asyncio.exceptions
import difflib
import glob
import logging
import random
from datetime import datetime, timedelta
from timeit import default_timer as timer
from typing import List, Union, Tuple
from urllib.parse import quote

from dis_snek import Snake
from dis_snek.models import (
    slash_command,
    InteractionContext,
    ComponentContext,
    Embed,
    ActionRow,
    Button,
    ButtonStyles,
    slash_option,
    SlashCommandChoice,
    AutocompleteContext,
    Message,
    Color,
    OptionTypes, Scale,
)

from cards import Card, Path, all_paths

paths = all_paths()


def find_card(card_name: str) -> Union[Tuple[Card, Path], Tuple[None, None]]:
    for path in paths:
        card = path.card_by_name(card_name)
        if card:
            return card, path
    return None, None


def path_by_name(valid_paths: List[Path], path_name: str) -> Path:
    return next((p for p in valid_paths if p.name == path_name), None)


# def build_links(raw_paths: List[Path]):
#     for path in raw_paths:
#         for card in path.cards:
#             if card.linked:
#                 linked_to = [c for c in path.cards if card.linked.find(c.name) > -1]
#             else:
#                 linked_to = [c for c in path.cards if (c.linked and c.linked.find(card.name) > -1)]
#             card.linked_to = linked_to if len(linked_to) > 0 else None


def card_url(card_name: str, path_name: str) -> str:
    base_url = "https://raw.githubusercontent.com/ShardlessBun/glorybound_cards/"
    version_string = 'v2.2.1'  # todo: add this as an environment variable
    url = f"{base_url}{quote(version_string)}/{quote(path_name)}/{quote(card_name)}.png"
    return url


def action_rows_from_path(path: Path, disabled_card: str = None) -> List[ActionRow]:
    rows = list()
    if not disabled_card:
        disabled_card = path.name

    # Make path button
    rows.append(ActionRow(Button(
        label=path.name,
        custom_id=path.name,
        style=ButtonStyles.SUCCESS,
        disabled=True if disabled_card == path.name else False
    )))

    # Make standard & linked card buttons
    std_cards = list()
    linked_cards = list()
    for card in path.cards:
        if not card.linked:
            btn = Button(
                label=card.name,
                custom_id=card.name,
                style=ButtonStyles.PRIMARY,
                disabled=True if disabled_card == card.name else False
            )
            std_cards.append(btn)

        else:
            linked_cards.append(Button(
                label=card.name,
                custom_id=card.name,
                style=ButtonStyles.SECONDARY,
                disabled=True if disabled_card == card.name else False
            ))
    rows.append(ActionRow(*std_cards))
    if len(linked_cards) > 0:
        rows.append(ActionRow(*linked_cards))

    return rows


def components_from_linked(card: Card) -> List[Button]:
    buttons = [Button(
        label=card.name,
        custom_id=card.name,
        style=ButtonStyles.SECONDARY if card.linked else ButtonStyles.PRIMARY,
        disabled=True
    )]
    for c in (card.linked_to or []):
        buttons.append(
            Button(
                label=c.name,
                custom_id=c.name,
                style=ButtonStyles.SECONDARY if c.linked else ButtonStyles.PRIMARY
            )
        )
    return buttons


def build_embed(path: Path, card: Card = None) -> Embed:
    embed = Embed(color=Color(int(path.colors[0], 16)))
    if card:
        embed.title = card.name
        if card.linked:
            embed.color = Color(int(path.colors[1], 16))
        embed.set_image(url=card_url(card.name, path.name))
    else:
        embed.title = f"Path of the {path.name}"
        embed.set_image(url=card_url(path.name, path.name))

    return embed


def path_choices(allowed_paths: List[Path]) -> List[SlashCommandChoice]:
    """
    Converts a list of Path objects into SlashCommandChoices

    :param allowed_paths: List of allowed Paths
    :return: List of slash command choices choices formatted for Discord
    """
    allowed_paths.sort(key=lambda x: x.name)
    return [SlashCommandChoice(path.name, path.name) for path in allowed_paths]


def determine_timeout(interaction_timeout: int) -> int:
    static_timeout = 60 * 5  # 5 minute limit between component interactions
    return static_timeout if static_timeout < interaction_timeout else interaction_timeout


def disable_all_but_id(interaction_components: Union[List[ActionRow], List[Button]],
                       custom_id: str) -> Union[List[ActionRow], List[Button]]:
    for cmp in interaction_components:
        if isinstance(cmp, Button):
            cmp.disabled = True if cmp.custom_id == custom_id else False
        else:
            for button in cmp.components:
                button.disabled = True if button.custom_id == custom_id else False
    return interaction_components


def disable_all(interaction_components: Union[List[ActionRow], List[Button]]) -> Union[List[ActionRow], List[Button]]:
    for cmp in interaction_components:
        if isinstance(cmp, Button):
            cmp.disabled = True
        else:
            for button in cmp.components:
                button.disabled = True
    return interaction_components


class CardView(object):
    _card: Tuple[Card, Path]
    _selected: Tuple[Card, Path]

    def __init__(self, card_name: str):
        card = find_card(card_name)
        if not card[0]:
            raise ValueError
        self._card = card
        self._selected = card

    def select(self, card_name: str):
        self._selected = find_card(card_name)

    def components(self) -> ActionRow:
        buttons = components_from_linked(self._card[0])
        for b in buttons:
            b.disabled = True if b.custom_id == self._selected[0].name else False
        return ActionRow(*buttons)

    def embed(self) -> Embed:
        return build_embed(self._selected[1], self._selected[0])

    def interactable(self) -> bool:
        """
        Whether this view has any components which can be interacted with
        :return: True if there are interactable components, otherwise False
        """
        if self._card[0].linked_to:
            return len(self._card[0].linked_to) > 0
        return False

    async def await_interactions(self, msg: Message, snek: Snake):
        expires: datetime = datetime.now() + timedelta(minutes=30)  # Global timeout at 30 minutes since interaction

        while True:
            try:
                interaction_timeout = expires - datetime.now()
                event = await snek.wait_for_component(messages=msg,
                                                      timeout=determine_timeout(interaction_timeout.seconds))

            except asyncio.exceptions.TimeoutError:
                logging.debug(f"Interaction for msg id [ {msg.id} ] timed out")
                rows = disable_all(msg.components)
                await msg.edit(content="Timed Out", components=rows)
                break
            else:
                start = timer()
                button_ctx: ComponentContext = event.context
                self.select(button_ctx.custom_id)
                end = timer()
                print(f"msg id [ {msg.id} ]: {button_ctx.author} interacted with [ {button_ctx.custom_id} ]. "
                      f"Response time: [ {end - start}s ]")
                # logging.debug(f"msg id [ {msg.id} ]: {button_ctx.author} clicked on: {button_ctx.custom_id}")
                await button_ctx.edit_origin(embeds=self.embed(), components=self.components())


class TournamentPackView(object):
    _heirlooms: List[Card]
    _paths: List[Path]
    _selected: Union[Card, Path]
    _selected_heirloom: Card
    _selected_path: Path

    def __init__(self, heirlooms: List[Card], selected_paths: List[Path]):
        self._heirlooms = heirlooms
        self._paths = selected_paths
        self._selected = selected_paths[0]
        self._selected_heirloom = heirlooms[0]
        self._selected_path = selected_paths[0]

    def select(self, name: str):
        if name in [c.name for c in self._heirlooms]:
            self._selected_heirloom = find_card(name)[0]
        elif name in [p.name for p in self._paths]:
            p = path_by_name(self._paths, name)
            self._selected = p
            self._selected_path = p
        elif name in [c.name for p in self._paths for c in p.cards]:
            self._selected = find_card(name)[0]
        else:
            return NameError

    def components(self) -> List[ActionRow]:
        components = []
        heirloom_row = ActionRow()
        for heirloom in self._heirlooms:
            heirloom_row.add_components(
                Button(
                    label=heirloom.name,
                    custom_id=heirloom.name,
                    style=ButtonStyles.SECONDARY,
                    disabled=True if heirloom.name == self._selected_heirloom.name else False
                ))
        components.append(heirloom_row)
        paths_row = ActionRow()
        for path in self._paths:
            paths_row.add_components(
                Button(
                    label=path.name,
                    custom_id=path.name,
                    style=ButtonStyles.SUCCESS,
                    disabled=True if path.name == self._selected.name else False
                ))
        components.append(paths_row)
        cards_rows = action_rows_from_path(self._selected_path, self._selected.name)
        cards_rows.pop(0)
        components.extend(cards_rows)
        return components

    def embeds(self) -> List[Embed]:
        heirloom_embed = build_embed(path_by_name(paths, 'Heirloom'), self._selected_heirloom)

        if isinstance(self._selected, Path):
            card_embed = build_embed(self._selected)
        else:
            card_embed = build_embed(self._selected_path, self._selected)

        return [heirloom_embed, card_embed]


class CardScale(Scale):

    def __init__(self, client: Snake):
        self.client = client

    @slash_command(name="path",
                   description="Display an entire path")
    @slash_option(name="path_name",
                  opt_type=OptionTypes.STRING,
                  description="Path to be displayed",
                  required=True,
                  choices=path_choices([p for p in all_paths() if p.name != 'Heirloom']))
    async def path_image(self, ctx: InteractionContext, path_name: str, ephemeral: bool = False):
        path = next((p for p in paths if p.name == path_name), None)

        embed = build_embed(path)
        rows = action_rows_from_path(path)
        msg = await ctx.send(embeds=embed, components=rows)
        expires: datetime = datetime.now() + timedelta(minutes=30,
                                                       seconds=0)  # Disable the whole thing after 30 minutes

        # Now wait for component interactions
        while True:
            try:
                interaction_timeout = expires - datetime.now()
                event = await self.client.wait_for_component(messages=msg,
                                                             timeout=determine_timeout(interaction_timeout.seconds))
            except asyncio.exceptions.TimeoutError:
                logging.debug(f"Interaction for msg id [ {msg.id} ] timed out")

                # Try to clean up the buttons no matter the exception
                rows = disable_all(rows)
                await msg.edit(content="Timed Out", components=rows)
                break
            else:
                start = timer()
                button_ctx: ComponentContext = event.context
                logging.debug(f"msg id [ {msg.id} ]: {button_ctx.author} clicked on: {button_ctx.custom_id}")

                if button_ctx.custom_id == path.name:
                    cmp_embed = build_embed(path)
                else:
                    card = path.card_by_name(button_ctx.custom_id)
                    cmp_embed = build_embed(path, card)

                rows = disable_all_but_id(rows, button_ctx.custom_id)
                end = timer()
                print(f"msg id [ {msg.id} ]: {button_ctx.author} interacted with [ {button_ctx.custom_id} ]. "
                      f"Response time: [ {end - start}s ]")
                await button_ctx.edit_origin(embeds=cmp_embed, components=rows)

    @slash_command(name="card",
                   description="Displays a card and all cards linked to it")
    @slash_option(name="card_name",
                  description="Card to be displayed",
                  required=True,
                  opt_type=OptionTypes.STRING,
                  autocomplete=True)
    async def card_image(self, ctx: InteractionContext, card_name: str, ephemeral: bool = False):
        card, path = find_card(card_name)
        if not card:
            await ctx.send(f"Error: card \'{card_name}\' not found", ephemeral=True)
            return

        card_view = CardView(card.name)

        msg = await ctx.send(embeds=card_view.embed(), components=card_view.components())
        if card_view.interactable():
            await card_view.await_interactions(msg, self.client)

    @card_image.autocomplete("card_name")
    async def autocomplete_cardname(self, ctx: AutocompleteContext, card_name: str):
        """
        Sends a list of autocomplete options back to Discord based on the partial card name provided

        :param ctx: The AutocompleteContext of the interaction
        :param card_name: The substring to match against
        """

        cards = {card.name.lower(): card.name for path in paths for card in path.cards}

        if len(card_name) <= 3:
            cutoff = 0
        elif 3 < len(card_name) <= 6:
            cutoff = 0.3
        else:
            cutoff = 0.5
        closest = difflib.get_close_matches(card_name.lower(), list(cards.keys()), n=10, cutoff=cutoff)

        filtered = list(filter(lambda c: card_name.lower() in c, closest))
        no_matches = list(filter(lambda c: card_name.lower() not in c, closest))
        filtered.extend(no_matches)

        closest_dicts = [{"name": cards[c], "value": cards[c]} for c in filtered]
        await ctx.send(choices=closest_dicts)

    @slash_command(name="tournamentpack",
                   description="Generates a combination of three heirlooms and three paths to simulate a tournament")
    @slash_option(name="hidden",
                  opt_type=OptionTypes.BOOLEAN,
                  description="Whether this should be hidden from other users. True by default.",
                  required=False)
    async def generate_paths(self, ctx: InteractionContext, hidden: bool = True):
        heirlooms = random.sample(path_by_name(paths, 'Heirloom').cards, 3)
        randpaths = random.sample([p for p in paths if p.name != 'Heirloom'], 3)

        pack_view = TournamentPackView(heirlooms, randpaths)
        msg = await ctx.send(embeds=pack_view.embeds(), components=pack_view.components(), ephemeral=hidden)
        expires: datetime = datetime.now() + timedelta(minutes=30)  # Global timeout at 30 minutes since interaction

        while True:
            try:
                interaction_timeout = expires - datetime.now()
                event = await self.client.wait_for_component(messages=msg,
                                                             timeout=determine_timeout(interaction_timeout.seconds))
            except asyncio.exceptions.TimeoutError:
                if not hidden:
                    logging.debug(f"Interaction for msg id [ {msg.id} ] timed out")

                    rows = disable_all(msg.components)
                    await msg.edit(content="Timed Out", embeds=[], components=rows)
                    break
            else:
                start = timer()
                button_ctx: ComponentContext = event.context
                # logging.debug(f"msg id [ {msg.id} ]: {button_ctx.author} clicked on: {button_ctx.custom_id}")

                pack_view.select(button_ctx.custom_id)
                end = timer()
                print(f"msg id [ {msg.id} ]: {button_ctx.author} interacted with [ {button_ctx.custom_id} ]. "
                      f"Response time: [ {end - start}s ]")
                # logging.debug(f"msg id [ {msg.id} ]: {button_ctx.author} interacted with [ {button_ctx.custom_id} ]. "
                #               f"Response time: [ {end - start}s ]")
                await button_ctx.edit_origin(embeds=pack_view.embeds(), components=pack_view.components())

    @slash_command(name="random_heirloom",
                   description="Displays a random heirloom")
    async def random_heirloom(self, ctx: InteractionContext):
        heirlooms = next(p for p in paths if p.name == "Heirloom")
        r_heirloom = random.choice(heirlooms.cards)

        cardview = CardView(r_heirloom.name)

        msg = await ctx.send(embeds=cardview.embed(), components=cardview.components())

        if cardview.interactable():
            await cardview.await_interactions(msg, self.client)

    @slash_command(name="random_card",
                   description="Displays a random (non-heirloom) card")
    async def random_pathcard(self, ctx: InteractionContext):
        r_cardname = random.choice([card.name for path in paths if path.name != "Heirloom" for card in path.cards])

        cardview = CardView(r_cardname)

        msg = await ctx.send(embeds=cardview.embed(), components=cardview.components())

        if cardview.interactable():
            await cardview.await_interactions(msg, self.client)


def setup(snek):
    CardScale(snek)
