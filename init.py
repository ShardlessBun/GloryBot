import logging
import os

from dis_snek import Snake
from dis_snek.models import slash_command, InteractionContext, Button, ButtonStyles, Embed


snek = Snake(
    sync_interactions=True,  # sync application commands with discord
    delete_unused_application_cmds=False,  # Delete commands that arent listed here
    debug_scope=os.environ.get('test_scope', False)  # Override the commands scope, and only create them in this guild
)

logging.basicConfig(filename='app.log', level=logging.DEBUG, filemode='w',
                    format='%(asctime)s: %(name)s - %(levelname)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')


@slash_command(name="invite",
               description="Gives a link you can use to invite this bot to your server")
async def invite_link(ctx: InteractionContext):
    await ctx.send(content="Click to add me to your server",
                   components=Button(
                       style=ButtonStyles.LINK,
                       label="Invite",
                       url="https://discord.com/api/oauth2/authorize?client_id=912433102108913756"
                           "&permissions=2147764224&scope=bot"
                   ))

snek.grow_scale("cardscale")
# snek.grow_scale("tournament")
snek.start(os.environ['bot_token'])
