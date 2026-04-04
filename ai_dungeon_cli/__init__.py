#!/usr/bin/env python3

import os
import sys
import asyncio
import requests

from abc import ABC, abstractmethod

from typing import Dict

from pprint import pprint

# NB: this is hackish but seems necessary when downloaded from pypi
main_path = os.path.dirname(os.path.realpath(__file__))
module_path = os.path.abspath(main_path)
if module_path not in sys.path:
    sys.path.append(module_path)

from impl.utils.debug_print import activate_debug, debug_print, debug_pprint
from impl.api.client import AiDungeonApiClient
from impl.adventure_state import AdventureStateStore
from impl.conf import Config
from impl.user_interaction import UserIo, TermIo, TermIoSlowStory


# -------------------------------------------------------------------------
# EXCEPTIONS

# Quit Session exception for easier error and exiting handling
class QuitSession(Exception):
    """raise this when the user typed /quit in order to leave the session"""


# -------------------------------------------------------------------------
# GAME LOGIC

class AbstractAiDungeonGame(ABC):
    def __init__(self, api: AiDungeonApiClient, conf: Config, user_io: UserIo):
        self.stop_session: bool = False

        self.user_id: str = None
        self.session_id: str = None

        self.scenario_id: str = '' # REVIEW: maybe call it setting_id ?
        self.character_name: str = ''
        self.adventure_id: str = ''
        self.public_id: str = None

        self.story_pitch_template: str = ''
        self.story_pitch: str = ''
        self.quests: str = ''

        self.setting_name: str = None
        self.is_multiplayer: bool = False
        self.story_configuration: Dict[str, str] = {}
        self.session: requests.Session = requests.Session()

        self.api = api
        self.conf = conf
        self.user_io = user_io

    def update_session_auth(self):
        self.session.headers.update({"X-Access-Token": self.conf.auth_token})

    def get_auth_token(self) -> str:
        return self.conf.auth_token

    def get_credentials(self):
        if self.conf.email and self.conf.password:
            return [self.conf.email, self.conf.password]

    def login(self, resume_adventure=None):
        pass

    def choose_selection(self, allowed_values: Dict[str, str], k_or_v='v') -> str:

        if k_or_v == 'k':
            allowed_values = {v: k for k, v in allowed_values.items()}

        while True:
            choice = self.user_io.handle_user_input()
            choice = choice.strip()

            if choice == "/quit":
                raise QuitSession("/quit")

            elif choice in allowed_values.keys():
                return allowed_values[choice]
            elif choice in allowed_values.values():
                    return choice
            else:
                self.user_io.handle_basic_output("Please enter a valid selection.")
                continue


    def make_user_choose_config(self):
        pass

    # Initialize story
    def init_story(self):
        pass

    def resume_story(self, session_id: str):
        pass

    # Function for when the input typed was ordinary
    def process_regular_action(self, user_input: str):
        pass

    # Function for when /remember is typed
    def process_remember_action(self, user_input: str):
        pass

    # Function that is called each iteration to process user inputs
    def process_next_action(self):
        user_input = self.user_io.handle_user_input()

        if user_input == "/quit":
            self.stop_session = True

        else:
            if user_input.startswith("/remember"):
                self.process_remember_action(user_input[len("/remember "):])
            else:
                self.process_regular_action(user_input)

    def start_game(self):
        # Run until /quit is received inside the process_next_action func
        while not self.stop_session:
            self.process_next_action()


## --------------------------------

class AiDungeonGame(AbstractAiDungeonGame):
    def __init__(self, api: AiDungeonApiClient, conf: Config, user_io: UserIo, state_store: AdventureStateStore):
        super().__init__(api, conf, user_io)
        self.state_store = state_store
        self.should_announce_resume = False


    def login(self, resume_adventure=None):
        auth_token = self.get_auth_token()

        if auth_token:
            self.api.update_session_access_token(auth_token)
        else:
            creds = self.get_credentials()
            if creds:
                email, password = creds
                self.api.user_login(email, password)
            else:
                stored_refresh_token = None
                stored_auth_token = None
                if resume_adventure:
                    stored_refresh_token = resume_adventure.get("refresh_token")
                    stored_auth_token = resume_adventure.get("auth_token")

                if stored_refresh_token:
                    try:
                        self.api.refresh_session_access_token(stored_refresh_token)
                        return
                    except RuntimeError:
                        pass

                if stored_auth_token:
                    self.api.update_session_access_token(stored_auth_token)
                    return

                self.api.anonymous_login()


    def _choose_character_name(self):
        print("Enter your character's name...\n")

        character_name = self.user_io.handle_user_input()

        if character_name == "/quit":
            raise QuitSession("/quit")

        self.character_name = character_name # TODO: create a setter instead


    def join_multiplayer(self):
        self.is_multiplayer = True
        self.character_name = self.conf.character_name
        self.adventure_id = self.run_with_spinner(
            "Joining adventure...",
            lambda: self.api.join_multi_adventure(self.conf.public_adventure_id),
        )

    def save_current_adventure(self):
        if not self.adventure_id:
            return None

        return self.state_store.save(
            adventure_id=self.adventure_id,
            short_id=self.api.adventure_short_id or self.public_id,
            short_code=self.api.adventure_short_code or self.public_id,
            character_name=self.character_name,
            auth_token=self.api.access_token,
            refresh_token=self.api.refresh_token,
        )

    def announce_resume_target(self):
        short_ref = self.api.adventure_short_id or self.public_id
        if not short_ref:
            return

        self.user_io.handle_basic_output(
            "Saved locally. Resume later with --resume-last or --resume %s" % short_ref
        )

    def maybe_announce_resume_target(self):
        if not self.should_announce_resume:
            return

        self.should_announce_resume = False
        self.announce_resume_target()

    def run_with_spinner(self, message: str, callback):
        self.user_io.start_spinner(message)
        try:
            return callback()
        finally:
            self.user_io.stop_spinner()


    def make_user_choose_config(self):
        # self.api.perform_init_handshake()

        ## SETTING SELECTION

        prompt, settings = self.api.get_options(self.api.single_player_mode_id)

        print(prompt + "\n")

        setting_select_dict = {}
        for i, setting in settings.items():
            setting_id, setting_name = setting
            print(str(i) + ") " + setting_name)
            setting_select_dict[str(i)] = setting_name
            # setting_select_dict['0'] = '0' # secret mode
        selected_i = self.choose_selection(setting_select_dict, 'k')
        setting_id, self.setting_name = settings[selected_i]
        self.scenario_id = setting_id

        if self.setting_name == "custom":
            return
        elif self.setting_name == "archive":
            while True:
                prompt, options = self.api.get_options(self.scenario_id)

                if options is None:
                    self.story_pitch_template = prompt
                    self._choose_character_name()
                    self.story_pitch = self.api.make_story_pitch(self.story_pitch_template,
                                                                self.character_name)
                    return

                print(prompt + "\n")

                select_dict = {}
                for i, option in options.items():
                    option_id, option_name = option
                    print(str(i) + ") " + option_name)
                    select_dict[str(i)] = option_name
                    # setting_select_dict['0'] = '0' # secret mode
                selected_i = self.choose_selection(select_dict, 'k')
                option_id, option_name = options[selected_i]
                self.scenario_id = option_id


        ## CHARACTER SELECTION

        prompt, characters = self.api.get_characters(self.scenario_id)

        print(prompt + "\n")

        character_select_dict = {}
        for i, character in characters.items():
            character_id, character_type = character
            print(str(i) + ") " + character_type)
            character_select_dict[str(i)] = character_type
        selected_i = self.choose_selection(character_select_dict, 'k')
        character_id, character_type = characters[selected_i]
        self.scenario_id = character_id # TODO: create a setter instead

        self._choose_character_name()

        ## PITCH

        self.story_pitch_template = self.api.get_story_template_for_scenario(self.scenario_id)
        self.story_pitch = self.api.make_story_pitch(self.story_pitch_template,
                                                     self.character_name)


    # Initialize story
    def init_story(self):
        saved_adventure = None
        if self.is_multiplayer:
            self.story_pitch = self.run_with_spinner(
                "Loading story...",
                lambda: self.api.init_story_multi_adventure(self.conf.public_adventure_id),
            )
        elif self.setting_name == "custom":
            self.init_story_custom()
            saved_adventure = self.save_current_adventure()
        else:
            self.adventure_id, self.public_id, self.story_pitch, self.quests = self.run_with_spinner(
                "Generating story...",
                lambda: self.api.init_story(self.scenario_id, self.story_pitch),
            )
            saved_adventure = self.save_current_adventure()

        self.user_io.handle_story_output(self.story_pitch)
        if saved_adventure:
            self.should_announce_resume = True

    def resume_story(self, resume_target=None):
        adventure = None

        if resume_target is None:
            adventure = self.state_store.get_last()
            if adventure is None:
                raise RuntimeError("No locally saved adventure was found. Start a story first or provide --resume.")
        else:
            adventure = self.state_store.find(resume_target)

        if adventure is None:
            adventure = self.api.resolve_adventure_identifier(resume_target)

        self.character_name = adventure.get("character_name") or self.character_name
        self.adventure_id, self.public_id, self.story_pitch, self.quests = self.run_with_spinner(
            "Loading story...",
            lambda: self.api.resume_story(adventure),
        )
        saved_adventure = self.save_current_adventure()
        self.user_io.handle_story_output(self.story_pitch)
        if saved_adventure:
            self.should_announce_resume = True


    def init_story_custom(self):
        self.user_io.handle_basic_output(
            "Enter a prompt that describes who you are and the first couple sentences of where you start out ex: "
            "'You are a knight in the kingdom of Larion. You are hunting the evil dragon who has been terrorizing "
            "the kingdom. You enter the forest searching for the dragon and see'"
        )
        user_story_pitch = self.user_io.handle_user_input()

        self.adventure_id, self.public_id, self.story_pitch, self.quests = self.run_with_spinner(
            "Generating story...",
            lambda: self.api.init_story(
                self.scenario_id,
                user_story_pitch,
            ),
        )


    def find_action_type(self, user_input: str):
        user_input = user_input.strip()
        action = 'do'
        if user_input == '':
            return (action, user_input)
        elif user_input.lower().startswith('/do '):
            user_input = user_input[len('/do '):]
            action = 'do'
        elif user_input.lower().startswith('/say '):
            user_input = user_input[len('/say '):]
            action = 'say'
        elif user_input.lower().startswith('/story '):
            user_input = user_input[len('/story '):]
            action = 'story'
        elif user_input.lower().startswith('you say "') and user_input[-1] == '"':
            user_input = user_input[len('you say "'):-1]
            action = 'say'
        elif user_input[0] == '"' and user_input[-1] == '"':
            user_input = user_input[1:-1]
            action = 'say'
        return (action, user_input)


    # Function for when the input typed was ordinary
    def process_regular_action(self, user_input: str):

        (action, user_input) = self.find_action_type(user_input)

        resp = self.run_with_spinner(
            "Thinking...",
            lambda: self.api.perform_regular_action(self.adventure_id, action, user_input, self.character_name),
        )

        self.user_io.handle_story_output(resp)

    def process_remember_action(self, user_input: str):
        self.api.perform_remember_action(user_input, self.adventure_id)

    def process_next_action(self):
        user_input = self.user_io.handle_user_input()

        if user_input == "/quit":
            self.maybe_announce_resume_target()
            self.stop_session = True

        else:
            if user_input.startswith("/remember"):
                # pass
                self.process_remember_action(user_input[len("/remember "):])
            else:
                self.process_regular_action(user_input)


# -------------------------------------------------------------------------
# MAIN

def main():
    term_io = None
    ai_dungeon = None

    try:
        # Initialize the configuration from config file
        file_conf = Config.loaded_from_file()
        cli_args_conf = Config.loaded_from_cli_args()
        conf = Config.merged([file_conf, cli_args_conf])

        if conf.debug:
            activate_debug()

        # Initialize the terminal I/O class
        if conf.slow_typing_effect:
            term_io = TermIoSlowStory(conf.prompt)
        else:
            term_io = TermIo(conf.prompt)

        api_client = AiDungeonApiClient()
        state_store = AdventureStateStore()

        resume_adventure = None
        if conf.resume_last:
            resume_adventure = state_store.get_last()
        elif conf.resume_target:
            resume_adventure = state_store.find(conf.resume_target)

        # Initialize the game logic class with the given auth_token and prompt
        ai_dungeon = AiDungeonGame(api_client, conf, term_io, state_store)

        # Clears the console
        term_io.clear()

        # Login
        ai_dungeon.login(resume_adventure)

        # Displays the splash image accordingly
        if term_io.get_width() >= 80:
            term_io.display_splash()

        # Loads the current session configuration
        if conf.public_adventure_id:
            ai_dungeon.join_multiplayer()
            ai_dungeon.init_story()
        elif conf.resume_last:
            ai_dungeon.resume_story()
        elif conf.resume_target:
            ai_dungeon.resume_story(conf.resume_target)
        else:
            ai_dungeon.make_user_choose_config()
            # Initializes the story
            ai_dungeon.init_story()

        # Starts the game
        ai_dungeon.start_game()

    except QuitSession:
        term_io.stop_spinner()
        term_io.handle_basic_output("Bye Bye!")

    except EOFError:
        if ai_dungeon:
            ai_dungeon.maybe_announce_resume_target()
        term_io.stop_spinner()
        term_io.handle_basic_output("Received Keyboard Interrupt. Bye Bye...")

    except KeyboardInterrupt:
        if ai_dungeon:
            ai_dungeon.maybe_announce_resume_target()
        term_io.stop_spinner()
        term_io.handle_basic_output("Received Keyboard Interrupt. Bye Bye...")

    except requests.exceptions.TooManyRedirects:
        term_io.stop_spinner()
        term_io.handle_basic_output("Exceded max allowed number of HTTP redirects, API backend has probably changed")
        exit(1)

    except requests.exceptions.HTTPError as err:
        term_io.stop_spinner()
        term_io.handle_basic_output("Unexpected response from API backend:")
        term_io.handle_basic_output(err)
        exit(1)

    except ConnectionError:
        term_io.stop_spinner()
        term_io.handle_basic_output("Lost connection to the Ai Dungeon servers")
        exit(1)

    except requests.exceptions.RequestException as err:
        term_io.stop_spinner()
        term_io.handle_basic_output("Totally unexpected exception:")
        term_io.handle_basic_output(err)
        exit(1)


if __name__ == "__main__":
    main()
