#!/usr/bin/env python

from StreamDeck.StreamDeck import DeviceManager
from HomeAssistantWS.RemoteWS import HomeAssistantWS
from ImageTile.Tile import ColorTile, ImageTile
import asyncio
import sys


class BaseValueAdjustor(object):
    def __init__(self, hass, entity_id, state_image):
        self.hass         = hass
        self.entity_id    = entity_id
        self.image        = state_image
        self.old_state    = None

    async def get_image(self, force=True):
        state = await self.hass.get_state(self.entity_id)

        if state == self.old_state and not force:
            return None
        else:
            self.old_state = state

        self.image.set_value(state)
        return self.image

    async def button_state_changed(self, state):
        pass


class BaseToggleAdjustor(object):
    def __init__(self, hass, entity_id, state_images):
        self.hass         = hass
        self.entity_id    = entity_id
        self.state_images = state_images
        self.old_state    = None

    async def get_image(self, force=True):
        state = await self.hass.get_state(self.entity_id)

        if state == self.old_state and not force:
            return None
        else:
            self.old_state = state

        return self.state_images.get(state, self.state_images[None])

    async def button_state_changed(self, state):
        if state is True:
            await self.hass.set_state(domain='homeassistant', service='toggle', entity_id=self.entity_id)


class ValueAdjustor(BaseValueAdjustor):
    def __init__(self, hass, image_dimensions, entity_id, name):
        state_image = ColorTile(image_dimensions, (0, 0, 0), name)
        super().__init__(hass, entity_id, state_image)


class LightAdjustor(BaseToggleAdjustor):
    def __init__(self, hass, image_dimensions, entity_id, name):
        state_images = {
            'on': ImageTile(image_dimensions, 'Assets/light_on.png', name),
            None: ImageTile(image_dimensions, 'Assets/light_off.png', name),
        }
        super().__init__(hass, entity_id, state_images)


class AutomationAdjustor(BaseToggleAdjustor):
    def __init__(self, hass, image_dimensions, entity_id, name):
        state_images = {
            'on': ImageTile(image_dimensions, 'Assets/automation_on.png', name),
            None: ImageTile(image_dimensions, 'Assets/automation_off.png', name),
        }
        super().__init__(hass, entity_id, state_images)


class DeckPageManager(object):
    def __init__(self, deck, pages):
        image_format = deck.key_image_format()
        image_dimensions = (image_format['width'], image_format['height'])

        self.deck         = deck
        self.key_layout   = self.deck.key_layout()
        self.pages        = pages
        self.current_page = None
        self.null_button_image = ColorTile(image_dimensions, (0, 0, 0))

    async def set_deck_page(self, name):
        self.current_page = self.pages.get(name, self.pages['home'])
        await self.update_page()

    async def update_page(self, force=True):
        rows, cols = self.key_layout

        for x in range(0, cols):
            for y in range(0, rows):
                button_index = (y * cols) + x
                adjustor   = self.current_page.get((x, y))

                if adjustor is not None:
                    button_image = await adjustor.get_image(force=force)
                elif not force:
                    button_image = self.null_button_image
                else:
                    button_image = None

                if button_image is not None:
                    self.deck.set_key_image(button_index, [b for b in button_image])

    async def button_state_changed(self, key, state):
        rows, cols = self.key_layout

        button_pos = (key % cols, key // cols)
        adjustor   = self.current_page.get(button_pos)
        if adjustor is not None:
            await adjustor.button_state_changed(state)


async def main(loop):
    deck = DeviceManager().enumerate()[0]
    hass = HomeAssistantWS('192.168.1.104')

    image_format = deck.key_image_format()
    image_dimensions = (image_format['width'], image_format['height'])

    deck_pages = {
        'home': {
            (0, 0): LightAdjustor(hass, image_dimensions,      'group.study_lights',       'Study'),
            (0, 1): LightAdjustor(hass, image_dimensions,      'light.mr_ed',              'Mr Ed'),
            (1, 1): LightAdjustor(hass, image_dimensions,      'light.desk_lamp',          'Desk Lamp'),
            (2, 1): LightAdjustor(hass, image_dimensions,      'light.study_bias',         'Bias Light'),
            (3, 1): AutomationAdjustor(hass, image_dimensions, 'group.study_automations',  'Auto Dim'),
            (4, 1): ValueAdjustor(hass, image_dimensions,      'sensor.study_temperature', 'Study\nTemp')
        }
    }
    deck_page_manager = DeckPageManager(deck, deck_pages)

    async def hass_state_changed(data):
        await deck_page_manager.update_page(force=False)

    async def steamdeck_key_state_changed(deck, key, state):
        await deck_page_manager.button_state_changed(key, state)

    await hass.connect()

    deck.open()
    deck.set_brightness(30)
    deck.set_key_callback_async(steamdeck_key_state_changed)

    await deck_page_manager.set_deck_page(None)
    await hass.subscribe_to_event('state_changed', hass_state_changed)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    if "--debug" in sys.argv:
        print("Debug enabled", flush=True)
        import warnings
        loop.set_debug(True)
        loop.slow_callback_duration = 0.2
        warnings.simplefilter('always', ResourceWarning)

    loop.run_until_complete(main(loop))
    loop.run_forever()