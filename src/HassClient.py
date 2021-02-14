#!/usr/bin/env python3

# vim: set expandtab:
#   Python StreamDeck HomeAssistant Client
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

from HomeAssistantWS.RemoteWS import HomeAssistantWS
from Tile.TileManager import TileManager

import StreamDeck.DeviceManager as StreamDeck
import logging
import asyncio
import yaml
import os
import operator


class Config(object):
    def __init__(self, filename):
        try:
            logging.info('Reading config file "{}"...'.format(filename))

            with open(filename, 'r', encoding='utf-8') as config_file:
                self.config = yaml.safe_load(config_file)
        except IOError:
            logging.error('Failed to read config file "{}"!'.format(filename))

            self.config = {}

    def get(self, path, default=None):
        value = default

        location = self.config
        for fragment in path.split('/'):
            location = location.get(fragment, None)
            if location is None:
                return default

            value = location or default

        return value


class ScreenSaver:
    def __init__(self, loop, deck):
        self.deck = deck

        deck.set_key_callback_async(self._handle_button_press)

    async def start(self, brightness, callback, timeout=0):
        self.brightness = brightness
        self.callback = callback
        self.timeout = timeout

        loop.create_task(self._loop())

    async def _loop(self):
        await self._set_on()

        if self.timeout == 0:
            return

        while True:
            await asyncio.sleep(1)

            if self.on:
                self.steps -= 1
                if self.steps < 0:
                    await self._set_off()

    async def _set_on(self):
        self.deck.set_brightness(self.brightness)
        self.steps = self.timeout
        self.on = True

    async def _set_off(self):
        self.deck.set_brightness(0)
        self.steps = 0
        self.on = False

    async def _handle_button_press(self, deck, key, state):
        if self.on:
            self.steps = self.timeout
            await self.callback(deck, key, state)
        else:
            if not state:
                await self._set_on()


async def main(loop, config):
    conf_deck_brightness = config.get('streamdeck/brightness', 20)
    conf_deck_screensaver = config.get('streamdeck/screensaver', 0)
    conf_hass_host = config.get('home_assistant/host', 'localhost')
    conf_hass_ssl = config.get('home_assistant/ssl', False)
    conf_hass_port = config.get('home_assistant/port', 8123)
    conf_hass_pw = config.get('home_assistant/api_password')
    conf_hass_token = config.get('home_assistant/api_token', os.environ['HASS_API_TOKEN'])

    decks = StreamDeck.DeviceManager().enumerate()
    if not decks:
        logging.error("No StreamDeck found.")
        return False

    deck = decks[0]
    hass = HomeAssistantWS(ssl=conf_hass_ssl, host=conf_hass_host, port=conf_hass_port)

    tiles = dict()
    pages = dict()

    tile_classes = getattr(__import__("Tile"), "Tile")

    # Build dictionary for the tile class templates given in the config file
    conf_tiles = config.get('tiles', [])
    for conf_tile in conf_tiles:
        conf_tile_type = conf_tile.get('type')
        conf_tile_class = conf_tile.get('class')
        conf_tile_states = conf_tile.get('states')

        tile_states = dict()
        for conf_tile_state in conf_tile_states:
            state = conf_tile_state.get('state')
            tile_states[state] = conf_tile_state

        tiles[conf_tile_type] = {
            'class': getattr(tile_classes, conf_tile_class),
            'states': tile_states,
        }

    # Load templates
    conf_templates = config.get('templates', [])
    templates = {}
    for conf_template in conf_templates:
        conf_template_name = conf_template.get('name')
        conf_template_tiles = conf_template.get('tiles', [])
        templates[conf_template_name] = conf_template_tiles

    # Build dictionary of tile pages
    conf_screens = config.get('screens', [])
    conf_defaults = config.get('defaults', {})
    for conf_screen in conf_screens:
        conf_screen_name = conf_screen.get('name')
        conf_screen_tiles = conf_screen.get('tiles')

        page_tiles = dict()
        for conf_screen_tile in conf_screen_tiles:
            conf_screen_tile_template = conf_screen_tile.get('template')
            conf_screen_tile_pos = conf_screen_tile.get('position')
            if conf_screen_tile_template is None:
                template_tiles = [{}]
            else:
                template_tiles = templates.get(conf_screen_tile_template)

            for template_tile in template_tiles:
                template_tile_pos = template_tile.get('position', [0, 0])
                tile = {**template_tile, **conf_screen_tile}
                tile['position'] = tile_pos = list(map(operator.add, conf_screen_tile_pos, template_tile_pos))
                print(tile)

                tile_type = tile.get('type')
                tile_class_info = tiles.get(tile_type)
                page_tiles[tuple(tile_pos)] = tile_class_info['class'](deck=deck, hass=hass, tile_class=tile_class_info, tile_info=tile, defaults=conf_defaults)

        pages[conf_screen_name] = page_tiles

    tile_manager = TileManager(deck, pages)

    async def hass_state_changed(data):
        await tile_manager.update_page(force_redraw=False)

    async def steamdeck_key_state_changed(deck, key, state):
        await tile_manager.button_state_changed(key, state)

    logging.info("Connecting to %s:%s...", conf_hass_host, conf_hass_port)
    await hass.connect(api_password=conf_hass_pw, api_token=conf_hass_token)

    deck.open()
    deck.reset()

    screensaver = ScreenSaver(loop=loop, deck=deck)
    await screensaver.start(brightness=conf_deck_brightness, callback=steamdeck_key_state_changed, timeout=conf_deck_screensaver)

    await tile_manager.set_deck_page(None)
    await hass.subscribe_to_event('state_changed', hass_state_changed)

    return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    loop = asyncio.get_event_loop()

    config = Config('config.yaml')
    if config.get('debug'):
        logging.info('Debug enabled')
        loop.set_debug(True)
        loop.slow_callback_duration = 0.15

    init_ok = loop.run_until_complete(main(loop, config))
    if init_ok:
        loop.run_forever()
