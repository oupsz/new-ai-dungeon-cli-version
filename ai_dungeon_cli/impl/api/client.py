import os
import time

import requests

from impl.utils.debug_print import debug_print, debug_pprint


# -------------------------------------------------------------------------
# API CLIENT

class AiDungeonApiClient:
    def __init__(self):
        self.graphql_url: str = 'https://api.aidungeon.com/graphql'
        self.firebase_api_key: str = os.environ.get("AIDUNGEON_FIREBASE_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Origin": "https://play.aidungeon.com",
            "Referer": "https://play.aidungeon.com/",
        })
        self.account_id: str = ''
        self.access_token: str = ''
        self.refresh_token: str = ''
        self.adventure_short_id: str = ''
        self.adventure_short_code: str = ''

        self.single_player_mode_id: str = '1r0T3TXT'

    def _require_firebase_api_key(self):
        if self.firebase_api_key:
            return

        raise RuntimeError(
            "Missing AIDUNGEON_FIREBASE_API_KEY. "
            "Export the Firebase web API key before starting the client."
        )


    def _execute_query(self, query, params=None):
        response = self.session.post(
            self.graphql_url,
            json={
                "query": query,
                "variables": params or {},
            },
            timeout=30,
        )
        payload = response.json()
        if not response.ok:
            raise RuntimeError(payload)
        if "errors" in payload:
            raise RuntimeError(payload["errors"])
        return payload["data"]


    def update_session_access_token(self, access_token):
        self.access_token = access_token
        self.session.headers.update({"Authorization": f"firebase {access_token}"})


    def user_login(self, email, password):
        self._require_firebase_api_key()
        debug_print("user login")
        response = self.session.post(
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            params={"key": self.firebase_api_key},
            json={
                "email": email,
                "password": password,
                "returnSecureToken": True,
            },
            timeout=30,
        )
        payload = response.json()
        if not response.ok:
            raise RuntimeError(payload)
        debug_print(payload)
        self.account_id = payload.get("localId", "")
        self.refresh_token = payload.get("refreshToken", "")
        self.update_session_access_token(payload["idToken"])


    def anonymous_login(self):
        self._require_firebase_api_key()
        debug_print("anonymous login")
        response = self.session.post(
            "https://identitytoolkit.googleapis.com/v1/accounts:signUp",
            params={"key": self.firebase_api_key},
            json={"returnSecureToken": True},
            timeout=30,
        )
        payload = response.json()
        if not response.ok:
            raise RuntimeError(payload)
        debug_print(payload)
        self.account_id = payload.get("localId", "")
        self.refresh_token = payload.get("refreshToken", "")
        self.update_session_access_token(payload["idToken"])

    def refresh_session_access_token(self, refresh_token):
        self._require_firebase_api_key()
        debug_print("refresh session access token")
        response = self.session.post(
            "https://securetoken.googleapis.com/v1/token",
            params={"key": self.firebase_api_key},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        payload = response.json()
        if not response.ok:
            raise RuntimeError(payload)
        debug_print(payload)
        self.account_id = payload.get("user_id", "")
        self.refresh_token = payload.get("refresh_token", refresh_token)
        self.update_session_access_token(payload["id_token"])



    def perform_init_handshake(self):
        # debug_print("query user details")
        # result = self._execute_query('''
        # {  user {    id    isDeveloper    hasPremium    lastAdventure {      id      mode      __typename    }    newProductUpdates {      id      title      description      createdAt      __typename    }    __typename  }}
        # ''')
        # debug_print(result)


        debug_print("add device token")
        result = self._execute_query('''
        mutation ($token: String, $platform: String) {  addDeviceToken(token: $token, platform: $platform)}
        ''',
                                     { 'token': 'web',
                                       'platform': 'web' })
        debug_print(result)


        debug_print("send event start premium")
        result = self._execute_query('''
        mutation ($input: EventInput) {  sendEvent(input: $input)}
        ''',
                                     {
                                         "input": {
                                             "eventName":"start_premium_v5",
                                             "variation":"dont",
                                             # "variation":"show",
                                             "platform":"web"
                                         }
                                     })
        debug_print(result)


    @staticmethod
    def normalize_options(raw_settings_list, current_short_id=None, top_level_only=False):
        settings_dict = {}
        filtered_options = []
        for opts in raw_settings_list or []:
            if opts['shortId'] == current_short_id:
                continue
            if top_level_only:
                child_options = opts.get('options') or []
                if len(child_options) <= 1 and opts.get('title') != 'custom':
                    continue
            filtered_options.append(opts)

        for i, opts in enumerate(filtered_options, start=1):
            setting_id = opts['shortId']
            setting_name = opts['title']
            settings_dict[str(i)] = [setting_id, setting_name]
        return settings_dict


    def _get_scenario(self, scenario_id):
        result = self._execute_query('''
        query ($shortId: String) {
            scenario(shortId: $shortId, viewPublished: true) {
                id
                shortId
                title
                options {
                    shortId
                    title
                    options {
                        shortId
                    }
                }
                state {
                    prompt
                }
            }
        }
        ''',
        {"shortId": scenario_id})
        return result['scenario']


    def _get_action_count(self):
        result = self._execute_query('''
        query ($shortId: String) {
            adventure(shortId: $shortId) {
                actionCount
            }
        }
        ''',
        {"shortId": self.adventure_short_id})
        return result['adventure']['actionCount']


    def _get_adventure_window(self, offset=0, page_size=4):
        result = self._execute_query('''
        query ($shortId: String, $offset: Int, $pageSize: Int) {
            adventure(shortId: $shortId) {
                id
                shortId
                shortCode
                actionCount
                read(offset: $offset, pageSize: $pageSize) {
                    actions {
                        id
                        type
                        text
                    }
                }
            }
        }
        ''',
        {
            "shortId": self.adventure_short_id,
            "offset": offset,
            "pageSize": page_size,
        })
        return result['adventure']

    def _get_adventure_by_short_id(self, short_id):
        result = self._execute_query('''
        query ($shortId: String) {
            adventure(shortId: $shortId) {
                id
                shortId
                shortCode
                actionCount
            }
        }
        ''',
        {"shortId": short_id})
        return result['adventure']

    def _get_adventure_by_id(self, adventure_id):
        result = self._execute_query('''
        query ($id: ID) {
            adventure(id: $id) {
                id
                shortId
                shortCode
                actionCount
            }
        }
        ''',
        {"id": adventure_id})
        return result['adventure']


    def _wait_for_new_continue(self, offset=0, timeout=30):
        deadline = time.time() + timeout
        last_snapshot = None

        while time.time() < deadline:
            snapshot = self._get_adventure_window(offset=offset, page_size=4)
            last_snapshot = snapshot
            actions = snapshot['read']['actions']
            if actions and actions[-1]['type'] == 'continue':
                return snapshot
            time.sleep(1)

        return last_snapshot

    def _get_latest_adventure_window(self, page_size=4):
        action_count = self._get_action_count()
        if action_count <= 0:
            return None

        page_size = max(page_size, 4)
        offset = max(action_count - page_size, 0)
        return self._get_adventure_window(offset=offset, page_size=page_size)

    @staticmethod
    def _latest_action(snapshot):
        if not snapshot:
            return None

        actions = snapshot['read']['actions']
        if not actions:
            return None

        return actions[-1]

    def _wait_for_latest_continue(self, previous_action_count=0, previous_last_action_id=None, timeout=30):
        deadline = time.time() + timeout

        while time.time() < deadline:
            snapshot = self._get_latest_adventure_window(page_size=4)
            latest_action = self._latest_action(snapshot)
            if snapshot is None or latest_action is None:
                time.sleep(1)
                continue

            action_count = snapshot.get('actionCount', 0)
            if action_count <= previous_action_count:
                time.sleep(1)
                continue

            if previous_last_action_id and latest_action['id'] == previous_last_action_id:
                time.sleep(1)
                continue

            if latest_action['type'] == 'continue':
                return snapshot

            time.sleep(1)

        raise RuntimeError(
            "AI Dungeon accepted the action but did not return a new continuation before timing out."
        )


    @staticmethod
    def _join_initial_story(actions):
        story_parts = []
        for action in actions:
            if action['type'] not in ['start', 'continue']:
                break
            story_parts.append(action['text'])
        return ''.join(story_parts)

    @staticmethod
    def _join_story_actions(actions):
        story_parts = []
        for action in actions:
            if action['type'] not in ['start', 'story', 'continue']:
                continue
            story_parts.append(action['text'])
        return ''.join(story_parts)

    @staticmethod
    def _normalize_adventure(adventure):
        if adventure is None:
            return None

        return {
            "adventure_id": adventure.get("id"),
            "short_id": adventure.get("shortId"),
            "short_code": adventure.get("shortCode"),
            "action_count": adventure.get("actionCount", 0),
        }


    def get_options(self, scenario_id):
        debug_print("query options")
        scenario = self._get_scenario(scenario_id)
        debug_print(scenario)

        prompt = scenario['state']['prompt'] or ''
        options = self.normalize_options(
            scenario['options'],
            current_short_id=scenario['shortId'],
            top_level_only=(scenario_id == self.single_player_mode_id),
        )
        return [prompt, options or None]


    def get_settings_single_player(self):
        return self.get_options(self.single_player_mode_id)

    def resolve_adventure_identifier(self, adventure_ref):
        errors = []

        try:
            adventure = self._normalize_adventure(self._get_adventure_by_short_id(adventure_ref))
            if adventure:
                return adventure
        except RuntimeError as err:
            errors.append(err)

        try:
            adventure = self._normalize_adventure(self._get_adventure_by_id(adventure_ref))
            if adventure:
                return adventure
        except RuntimeError as err:
            errors.append(err)

        if errors:
            raise RuntimeError(errors[-1])
        raise RuntimeError("Could not resolve adventure: %s" % adventure_ref)

    def activate_adventure(self, adventure):
        self.adventure_short_id = adventure["short_id"]
        self.adventure_short_code = adventure.get("short_code") or ''

    def get_recent_story(self, action_count=None, page_size=8):
        if action_count is None:
            action_count = self._get_action_count()

        page_size = max(page_size, 4)
        offset = max(action_count - page_size, 0)
        snapshot = self._get_adventure_window(offset=offset, page_size=page_size)
        actions = snapshot['read']['actions']
        return self._join_story_actions(actions)


    def join_multi_adventure(self, public_adventure_id):
        debug_print("join multi-user adventure")
        result = self._execute_query('''
        mutation ($shortCode: String!) {
            joinMultiplayerAdventure(shortCode: $shortCode) {
                code
                success
                message
                adventure {
                    id
                    shortId
                    shortCode
                }
            }
        }
        ''',
        {"shortCode": public_adventure_id})
        debug_print(result)
        response = result['joinMultiplayerAdventure']
        if not response['success']:
            raise RuntimeError(response['message'])

        self.adventure_short_id = response['adventure']['shortId']
        self.adventure_short_code = response['adventure']['shortCode']
        return response['adventure']['id']


    def get_characters(self, scenario_id):
        debug_print("query characters")
        scenario = self._get_scenario(scenario_id)
        debug_print(scenario)

        prompt = scenario['state']['prompt'] or ''
        characters = self.normalize_options(
            scenario['options'],
            current_short_id=scenario['shortId'],
        )
        return [prompt, characters]


    def get_story_template_for_scenario(self, scenario_id):
        debug_print("query get story for scenario")
        scenario = self._get_scenario(scenario_id)
        debug_print(scenario)
        return scenario['state']['prompt'] or ''

    @staticmethod
    def initial_story_from_history_list(history_list):
        pitch = ''
        for entry in history_list:
            if not entry['type'] in ['story', 'continue']:
                break
            pitch += entry['text']
        return pitch


    def make_story_pitch(self, story_pitch_template, character_name):
        return story_pitch_template.replace('${character.name}', character_name)


    def init_custom_story_pitch(self, adventure_id, user_input):
        previous_action_count = self._get_action_count()
        previous_snapshot = self._get_latest_adventure_window(page_size=4)
        previous_last_action = self._latest_action(previous_snapshot)
        previous_last_action_id = previous_last_action['id'] if previous_last_action else None

        debug_print("send custom settings story pitch")
        result = self._execute_query('''
        mutation ($input: ActionInput!) {
            addAction(input: $input) {
                code
                success
                message
            }
        }
        ''',
        {
            "input": {
                "adventureId": adventure_id,
                "type": "story",
                "text": user_input,
            }
        })
        debug_print(result)

        response = result['addAction']
        if not response['success']:
            raise RuntimeError(response.get('message') or "AI Dungeon rejected the custom story prompt.")

        snapshot = self._wait_for_latest_continue(
            previous_action_count=previous_action_count,
            previous_last_action_id=previous_last_action_id,
        )
        if not snapshot or not snapshot['read']['actions']:
            return user_input
        return snapshot['read']['actions'][-1]['text']


    def create_adventure(self, scenario_id, story_pitch):
        debug_print("create adventure")
        result = self._execute_query('''
        mutation ($scenarioShortId: String, $prompt: String) {
            playAdventure(scenarioShortId: $scenarioShortId, prompt: $prompt, viewPublished: true) {
                code
                success
                message
                adventure {
                    id
                    shortId
                    shortCode
                }
            }
        }
        ''',
        {
            "scenarioShortId": scenario_id,
            "prompt": story_pitch,
        })
        debug_print(result)
        response = result['playAdventure']
        if not response['success'] or response['adventure'] is None:
            raise RuntimeError(response['message'])

        adventure = response['adventure']
        self.adventure_short_id = adventure['shortId']
        self.adventure_short_code = adventure['shortCode']
        return [adventure['id'], story_pitch]


    def init_story_multi_adventure(self, public_adventure_id):
        debug_print("get story multi-user adventure")
        result = self._get_adventure_window(offset=0, page_size=20)
        debug_print(result)
        entries = []
        for entry in result['read']['actions']:
            entry = entry['text']
            if entry.startswith("\n>"):
                entry = "\n" + entry + "\n"
            entries.append(entry)
        return ''.join(entries)


    def init_story(self, scenario_id, story_pitch):
        adventure_id, story_pitch = self.create_adventure(scenario_id, story_pitch)
        snapshot = self._wait_for_new_continue(offset=0)
        if snapshot and snapshot['read']['actions']:
            story_pitch = self._join_initial_story(snapshot['read']['actions']) or story_pitch

        return [adventure_id, self.adventure_short_code or self.adventure_short_id, story_pitch, ""]

    def resume_story(self, adventure):
        if isinstance(adventure, str):
            adventure = self.resolve_adventure_identifier(adventure)

        self.activate_adventure(adventure)

        action_count = adventure.get("action_count", 0)
        story_pitch = self.get_recent_story(action_count=action_count)
        return [
            adventure["adventure_id"],
            self.adventure_short_code or self.adventure_short_id,
            story_pitch,
            "",
        ]



    def perform_remember_action(self, user_input, adventure_id):
        debug_print("remember something")
        result = self._execute_query('''
        mutation ($input: AdventurePlotInput) {
            updateAdventurePlot(input: $input) {
                code
                success
                message
            }
        }
        ''',
        {
            "input": {
                "shortId": self.adventure_short_id,
                "memory": user_input,
            }
        })
        debug_print(result)


    def perform_regular_action(self, adventure_id, action, user_input, character_name = None):
        previous_action_count = self._get_action_count()
        previous_snapshot = self._get_latest_adventure_window(page_size=4)
        previous_last_action = self._latest_action(previous_snapshot)
        previous_last_action_id = previous_last_action['id'] if previous_last_action else None

        debug_print("send regular action")
        result = self._execute_query('''
        mutation ($input: ActionInput!) {
            addAction(input: $input) {
                code
                success
                message
            }
        }
        ''',
        {
            "input": {
                "adventureId": adventure_id,
                "type": action,
                "text": user_input,
                "characterName": character_name,
            }
        })
        debug_print(result)

        response = result['addAction']
        if not response['success']:
            raise RuntimeError(response.get('message') or "AI Dungeon rejected the action.")

        debug_print("get story continuation")
        snapshot = self._wait_for_latest_continue(
            previous_action_count=previous_action_count,
            previous_last_action_id=previous_last_action_id,
        )
        debug_print(snapshot)
        if not snapshot or not snapshot['read']['actions']:
            return ""

        return snapshot['read']['actions'][-1]['text']
