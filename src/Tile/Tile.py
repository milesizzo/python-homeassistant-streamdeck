# vim: set expandtab:
#   Python StreamDeck HomeAssistant Client
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

from .TileImage import TileImage


class BaseTile(object):
    def __init__(self, deck, hass=None, tile_class=None, tile_info=None, defaults=None):
        self.deck = deck
        self.hass = hass
        self.tile_class = tile_class
        self.tile_info = tile_info
        self.defaults = defaults or {}

        self.image_tile = TileImage(deck)
        self.old_state = None

    @property
    async def state(self):
        return None

    @property
    async def attributes(self):
        return {}

    def get_state_value(self, state_tile, key):
        return state_tile.get(key, self.defaults.get(key))

    async def get_image(self, force=True):
        state = await self.state

        if state == self.old_state and not force:
            return None

        self.old_state = state

        if self.tile_class is None:
            return self.image_tile

        state_tile = self.tile_class['states'].get(state) or self.tile_class['states'].get(None) or {}
        state_value = lambda key, default=None: state_tile.get(key, self.defaults.get(key, default))

        attributes = await self.attributes
        format_dict = {'state': state, **self.tile_info, **attributes}

        image_tile = self.image_tile
        image_tile.color = state_value('color')
        image_tile.overlay = state_value('overlay')
        image_tile.overlay_mode = state_value('overlay_mode')
        image_tile.label = state_value('label', '').format_map(format_dict)
        image_tile.label_font = state_value('label_font')
        image_tile.label_size = state_value('label_size')
        image_tile.value = state_value('value', '').format_map(format_dict)
        image_tile.value_font = state_value('value_font')
        image_tile.value_size = state_value('value_size')

        return image_tile

    async def button_state_changed(self, tile_manager, state):
        pass


class HassTile(BaseTile):
    def __init__(self, deck, hass, tile_class, tile_info, defaults):
        super().__init__(deck, hass, tile_class, tile_info, defaults)

    async def get_hass_state(self):
        return await self.hass.get_state(self.tile_info['entity_id'])

    @property
    async def state(self):
        hass_state = await self.get_hass_state()
        return hass_state.get('state')

    @property
    async def attributes(self):
        hass_state = await self.get_hass_state()
        return hass_state.get('attributes')

    async def button_state_changed(self, tile_manager, state):
        if not state:
            return

        curr_state = await self.state
        state_info = self.tile_class['states'].get(curr_state) or self.tile_class['states'].get(None) or None
        if state_info is None:
            return
        action = state_info.get('action')
        if action is None:
            return
        action = action.split('/')

        if len(action) == 1:
            domain = 'homeassistant'
            service = action[0]
        else:
            domain = action[0]
            service = action[1]

        await self.hass.set_state(domain=domain, service=service, entity_id=self.tile_info['entity_id'])


class PageTile(BaseTile):
    def __init__(self, deck, hass, tile_class, tile_info, defaults):
        super().__init__(deck, hass, tile_class, tile_info, defaults)

    async def button_state_changed(self, tile_manager, state):
        if not state:
            return

        page_name = self.tile_info.get('page')
        await tile_manager.set_deck_page(page_name)
