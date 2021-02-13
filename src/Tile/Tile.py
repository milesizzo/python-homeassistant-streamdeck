# vim: set expandtab:
#   Python StreamDeck HomeAssistant Client
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

from .TileImage import TileImage


class BaseTile(object):
    def __init__(self, deck, hass=None, tile_class=None, tile_info=None):
        self.deck = deck
        self.hass = hass
        self.tile_class = tile_class
        self.tile_info = tile_info

        self.image_tile = TileImage(deck)
        self.old_state = None

    @property
    async def state(self):
        return None

    @property
    async def attributes(self):
        return {}

    async def get_image(self, force=True):
        state = await self.state

        if state == self.old_state and not force:
            return None

        self.old_state = state

        if self.tile_class is None:
            return self.image_tile

        state_tile = self.tile_class['states'].get(state) or self.tile_class['states'].get(None) or {}

        attributes = await self.attributes
        format_dict = {'state': state, **self.tile_info, **attributes}

        image_tile = self.image_tile
        image_tile.color = state_tile.get('color')
        image_tile.overlay = state_tile.get('overlay')
        image_tile.overlay_mode = state_tile.get('overlay_mode')
        image_tile.label = state_tile.get('label', '').format_map(format_dict)
        image_tile.label_font = state_tile.get('label_font')
        image_tile.label_size = state_tile.get('label_size')
        image_tile.value = state_tile.get('value', '').format_map(format_dict)
        image_tile.value_font = state_tile.get('value_font')
        image_tile.value_size = state_tile.get('value_size')

        return image_tile

    async def button_state_changed(self, tile_manager, state):
        pass


class HassTile(BaseTile):
    def __init__(self, deck, hass, tile_class, tile_info):
        super().__init__(deck, hass, tile_class, tile_info)

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
    def __init__(self, deck, hass, tile_class, tile_info):
        super().__init__(deck, hass, tile_class, tile_info)

    async def button_state_changed(self, tile_manager, state):
        if not state:
            return

        page_name = self.tile_info.get('page')
        await tile_manager.set_deck_page(page_name)
