import logging
import os

from dis_snek import Snake


snek = Snake(
    sync_interactions=True,  # sync application commands with discord
    delete_unused_application_cmds=False,  # Delete commands that arent listed here
    debug_scope=os.environ.get('test_scope', None)  # Override the commands scope, and only create them in this guild
)

logging.basicConfig(filename='app.log', level=logging.DEBUG, filemode='w',
                    format='%(asctime)s: %(name)s - %(levelname)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

snek.grow_scale("cardscale")
# snek.grow_scale("tournament")
snek.start(os.environ['bot_token'])
