import array
import json
import math
import os
import random
import sys
import urllib.error
import urllib.request

import pygame


WHITE = (255, 255, 255)
BG = (15, 20, 28)
PANEL = (24, 31, 43)
BORDER = (70, 78, 92)
EMPTY_FILL = (21, 27, 38)
TEXT = (243, 246, 252)
MUTED_TEXT = (171, 180, 194)
GREEN = (72, 149, 107)
YELLOW = (196, 168, 74)
GRAY = (84, 92, 106)
BUTTON = (55, 124, 197)
BUTTON_HOVER = (72, 146, 222)
BUTTON_SELECTED = (210, 162, 74)
BUTTON_DISABLED = (62, 68, 80)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORDS_FILE = os.path.join(BASE_DIR, "words.json")
BLOCKS_FILE = os.path.join(BASE_DIR, "blocks.json")
COMMON_WORDS_FILE = os.path.join(BASE_DIR, "common_words.json")
WORDLE5_ANSWERS_FILE = os.path.join(BASE_DIR, "wordle5_answers.txt")
WORDLE5_ANSWERS_URL = "https://gist.githubusercontent.com/cfreshman/a03ef2cba789d8cf00c08f767e0fad7b/raw"
WORDLE5_GUESSES_URL = "https://gist.githubusercontent.com/prichey/95db6bdef37482ba3f6eb7b4dec99101/raw"
SAMPLE_RATE = 22050

ESSENTIAL_WORDS = """
back note book door home love make take game word time work play help food rain snow
fire wind tree bird fish star moon blue room wall road land lake hill gold hand head
foot face hair mail milk meat rice song tale talk walk wait wake warm wash wish wood
yard year zone bank call camp card care case cast city cold come cook cool copy cost
crew dark date dead deal dear deep dish down draw drop drug drum duck duty each east
easy edge face fact fair fall farm fast fear feed feel feet fill film find fine firm
fish five flag flat flow fold folk font fool ford fork form fort foul four free frog
from fuel full fund gain gate gave gear gift girl give glad glow glue goal goes golf
gone good grab gray grew grip grow gulf hair half hall hang hard harm hate have hawk
heal heap hear heat held hell help hide high hike hill hint hold hole holy hook hope
horn host hour hunt hurt icon idea inch into iron item join joke jump jury just keen
keep kick kill kind king kiss knee knew knit know lace lack lady laid lake lamp land
lane last late lead leaf lean left lend less life lift like line link list live load
loan lock logo long look loop lord lose loss loud luck lung mail main make male mall
many mark mask mass mate meal mean meat meet melt menu mile mind mine mint miss mode
mold mood moon moss most move much must mute nail name navy near neat neck need nest
news next nice nine node none noon nose noun only onto open oral over pace pack page
paid pain pair pale palm park part pass past path peak pick pile pine pink pipe plan
plot plug plus poem poet pole poll pond pool poor port pose post pour pull pump pure
push quit race rack rail rain rank rare rate read real rear reed rely rent rest rice
rich ride ring ripe rise risk road rock role roll roof root rope rose ruin rule rush
rust safe sage sail sake sale salt same sand save scan seal seat seed seek seem seen
self sell send sent ship shop shot show shut sick side sign sing sink site size skin
skip slim slip slow snow soap soft soil sold sole some song soon sore sort soul soup
sour span spin spot stay stem step stir stop such suit sure surf swim tail take tall
tank tape task team tear tell tent term test text than that them then they thin this
tide tidy tile till tire told toll tone took tool tops tour town tree trip true tube
tuck tune turn twin type ugly unit upon urge used user vary vast verb very vest vice
view visa void volt vote wage wake walk want ward warm warn wash wave weak wear week
well went were west what when wife wild will wind wine wing wink wire wise wish with
wolf wood wool work worm worn wrap yard year yell yoga your zero zone
apple house water stone block about great think world never light night music paper
""".split()


class SoundManager:

    def __init__(self):
        self.enabled = True
        self.sounds = {}

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self._build_sounds()
        except pygame.error:
            self.enabled = False

    def _envelope(self, index, total):
        attack = max(1, int(total * 0.08))
        release = max(1, int(total * 0.35))
        if index < attack:
            return index / attack
        if index > total - release:
            return max(0.0, (total - index) / release)
        return 1.0

    def _tone(self, frequency, duration_ms, volume=0.3):
        sample_count = int(SAMPLE_RATE * duration_ms / 1000)
        samples = array.array("h")

        for index in range(sample_count):
            time = index / SAMPLE_RATE
            fade = self._envelope(index, sample_count)
            value = int(32767 * volume * fade * math.sin(2 * math.pi * frequency * time))
            samples.append(value)

        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _build_sounds(self):
        self.sounds = {
            "type": self._tone(620, 35, 0.18),
            "backspace": self._tone(420, 40, 0.2),
            "submit": self._tone(500, 55, 0.22),
            "correct": self._tone(720, 95, 0.32),
            "present": self._tone(520, 85, 0.28),
            "absent": self._tone(260, 75, 0.24),
            "hint": self._tone(900, 110, 0.3),
            "invalid": self._tone(180, 140, 0.35),
            "click": self._tone(700, 30, 0.16),
            "win": self._build_win_jingle(),
            "lose": self._build_lose_jingle(),
        }

    def _build_win_jingle(self):
        notes = [(523, 70), (659, 70), (784, 90), (988, 140)]
        return self._merge_notes(notes, 0.3)

    def _build_lose_jingle(self):
        notes = [(392, 100), (330, 100), (262, 160)]
        return self._merge_notes(notes, 0.26)

    def _merge_notes(self, notes, volume):
        merged = array.array("h")
        for frequency, duration_ms in notes:
            sample_count = int(SAMPLE_RATE * duration_ms / 1000)
            for index in range(sample_count):
                time = index / SAMPLE_RATE
                fade = self._envelope(index, sample_count)
                value = int(32767 * volume * fade * math.sin(2 * math.pi * frequency * time))
                merged.append(value)
        return pygame.mixer.Sound(buffer=merged.tobytes())

    def play(self, name):
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def play_reveal(self, state):
        if state in ("correct", "present", "absent"):
            self.play(state)

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled


class WordManager:
    def __init__(self):
        self.words_file = WORDS_FILE
        self.blocks_file = BLOCKS_FILE
        self.common_words_file = COMMON_WORDS_FILE
        self.solution_words = {"classic": {}, "minecraft": {}}
        self.ensure_common_words_file()

        classic_words = self.merge_word_groups(
            self.load_classic_words(),
            self.load_common_words(),
        )
        classic_words = self.merge_word_groups(
            classic_words,
            self.group_words_by_length(ESSENTIAL_WORDS),
        )
        self.mode_words = {
            "classic": classic_words,
            "minecraft": self.load_minecraft_words(),
        }
        self.solution_words["classic"] = self.build_solution_words("classic", classic_words)
        self.solution_words["minecraft"] = self.build_solution_words(
            "minecraft",
            self.mode_words["minecraft"],
        )

    def normalize_word(self, word):
        return word.strip().lower()

    def group_words_by_length(self, words):
        grouped = {length: [] for length in range(4, 8)}

        for word in words:
            if not isinstance(word, str):
                continue

            clean_word = self.normalize_word(word)

            if not clean_word.isalpha():
                continue

            word_length = len(clean_word)
            if word_length < 4 or word_length > 7:
                continue

            if clean_word not in grouped[word_length]:
                grouped[word_length].append(clean_word)

        result = {}
        for length in grouped:
            if grouped[length]:
                grouped[length].sort()
                result[length] = grouped[length]

        return result

    def merge_word_groups(self, base, extra):
        merged = {length: list(words) for length, words in base.items()}

        for length, words in extra.items():
            if length not in merged:
                merged[length] = []
            for word in words:
                if word not in merged[length]:
                    merged[length].append(word)
            merged[length].sort()

        return merged

    def ensure_common_words_file(self):
        if os.path.exists(self.common_words_file):
            return

        words = set(ESSENTIAL_WORDS)
        try:
            for url in (WORDLE5_ANSWERS_URL, WORDLE5_GUESSES_URL):
                with urllib.request.urlopen(url, timeout=20) as response:
                    for line in response.read().decode("utf-8").splitlines():
                        word = self.normalize_word(line)
                        if word.isalpha() and 4 <= len(word) <= 7:
                            words.add(word)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

        payload = {"words": sorted(words)}
        try:
            with open(self.common_words_file, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False)
        except OSError:
            pass

    def load_common_words(self):
        if not os.path.exists(self.common_words_file):
            return {}

        try:
            with open(self.common_words_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            return {}

        if not isinstance(data, dict) or not isinstance(data.get("words"), list):
            return {}

        return self.group_words_by_length(data["words"])

    def load_wordle5_answers(self):
        if not os.path.exists(WORDLE5_ANSWERS_FILE):
            return []

        try:
            with open(WORDLE5_ANSWERS_FILE, "r", encoding="utf-8") as file:
                lines = file.read().splitlines()
        except OSError:
            return []

        answers = []
        for line in lines:
            word = self.normalize_word(line)
            if len(word) == 5 and word.isalpha():
                answers.append(word)
        return answers

    def build_solution_words(self, mode, grouped_words):
        solutions = {}
        common_set = {
            length: set(words)
            for length, words in self.load_common_words().items()
        }
        wordle5_answers = set(self.load_wordle5_answers())

        for length, words in grouped_words.items():
            preferred = []
            for word in words:
                if length == 5 and word in wordle5_answers:
                    preferred.append(word)
                elif word in common_set.get(length, set()):
                    preferred.append(word)

            solutions[length] = preferred if preferred else list(words)

        return solutions

    def load_classic_words(self):
        try:
            with open(self.words_file,
                      "r",
                      encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError("Missing words.json")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in words.json")

        if not isinstance(data, dict) or "words" not in data:
            raise ValueError("words.json must contain an object with a 'words' key.")

        if not isinstance(data["words"], list):
            raise ValueError("'words' in words.json must be a list.")

        grouped_words = self.group_words_by_length(data["words"])
        if not grouped_words:
            raise ValueError("words.json does not contain valid words with length 4-7.")

        return grouped_words

    def load_minecraft_words(self):
        try:
            with open(self.blocks_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError("Missing blocks.json")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in blocks.json")

        if not isinstance(data, list):
            raise ValueError("blocks.json must contain a list.")

        block_words = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                block_name = item["name"].replace("_", "").lower()
                block_words.append(block_name)

        grouped_words = self.group_words_by_length(block_words)
        if not grouped_words:
            raise ValueError("blocks.json does not contain valid block names with length 4-7.")

        return grouped_words

    def get_available_lengths(self, mode):
        if mode not in self.mode_words:
            raise ValueError(f"Unknown mode: {mode}")
        lengths = list(self.mode_words[mode].keys())
        lengths.sort()
        return lengths

    def get_mode_words(self, mode, word_length):
        if mode not in self.mode_words:
            raise ValueError(f"Unknown mode: {mode}")

        if word_length not in self.mode_words[mode]:
            raise ValueError(f"This word length {word_length} is not available for {mode} mode.")

        return self.mode_words[mode][word_length]

    def choose_word(self, mode, word_length):
        solutions = self.solution_words.get(mode, {})
        if word_length in solutions and solutions[word_length]:
            return random.choice(solutions[word_length])
        return random.choice(self.get_mode_words(mode, word_length))

    def is_valid_word(self, word, mode, word_length):
        words = self.get_mode_words(mode, word_length)
        return word.lower() in words


# ==================== TILE ====================
class Tile:
    def __init__(self, row, col, rect):
        self.row = row
        self.col = col
        self.rect = rect
        self.letter = ""
        self.state = "empty"
        self.flip_progress = 1.0
        self.revealing = False
        self.reveal_color = GRAY
        self.is_hint = False
        self.reveal_sound_played = False

    def clear(self):
        self.letter = ""
        self.state = "empty"
        self.flip_progress = 1.0
        self.revealing = False
        self.reveal_color = GRAY
        self.is_hint = False
        self.reveal_sound_played = False

    def set_data(self, letter, is_hint=False):
        self.letter = letter.upper()
        self.is_hint = is_hint and bool(letter)

    def start_reveal(self, state, color):
        self.state = state
        self.reveal_color = color
        self.flip_progress = 1.0
        self.revealing = True
        self.reveal_sound_played = False

    def update(self, delta_time, on_reveal=None):
        if self.revealing:
            previous_progress = self.flip_progress
            self.flip_progress -= delta_time * 4.5
            if (
                on_reveal
                and not self.reveal_sound_played
                and previous_progress > 0
                and self.flip_progress <= 0
            ):
                self.reveal_sound_played = True
                on_reveal(self.state)
            if self.flip_progress <= -1.0:
                self.flip_progress = 1.0
                self.revealing = False

    def get_color(self):
        if self.state == "correct":
            return GREEN
        if self.state == "present":
            return YELLOW
        if self.state == "absent":
            return GRAY
        return EMPTY_FILL

    def draw(self, screen, font):
        color = self.get_color()
        border_color = BORDER
        if self.state != "empty":
            border_color = color

        display_rect = self.rect.copy()
        if self.revealing:
            scale = abs(self.flip_progress)
            display_rect.height = max(6, int(self.rect.height * scale))
            display_rect.centery = self.rect.centery
            if self.flip_progress < 0:
                color = self.reveal_color
                border_color = self.reveal_color

        shadow_rect = display_rect.move(0, 3)
        pygame.draw.rect(screen, (10, 14, 20), shadow_rect, border_radius=8)
        pygame.draw.rect(screen, color, display_rect, border_radius=8)
        pygame.draw.rect(screen, border_color, display_rect, width=2, border_radius=6)

        if self.letter:
            text_surface = font.render(self.letter, True, TEXT)
            text_rect = text_surface.get_rect(center=display_rect.center)
            screen.blit(text_surface, text_rect)

        if self.is_hint and display_rect.height > 14:
            self.draw_bulb(screen, display_rect)

    def draw_bulb(self, screen, rect):
        bulb_color = (244, 208, 63)
        outline_color = (140, 105, 18)
        center_x = rect.right - 13
        center_y = rect.top + 14
        radius = max(4, min(7, rect.width // 9))
        pygame.draw.circle(screen, bulb_color, (center_x, center_y), radius)
        pygame.draw.circle(screen, outline_color, (center_x, center_y), radius, width=1)

        base_rect = pygame.Rect(0, 0, radius + 3, max(4, radius - 1))
        base_rect.midtop = (center_x, center_y + radius - 1)
        pygame.draw.rect(screen, outline_color, base_rect, border_radius=2)

        start_pos = (center_x, center_y + radius + 3)
        end_pos = (center_x, center_y + radius + 7)
        pygame.draw.line(screen, outline_color, start_pos, end_pos, width=2)


# ==================== GRID ====================
class Grid:
    def __init__(self, x, y, rows=6, cols=5, tile_size=62, gap=8):
        self.rows = rows
        self.cols = cols
        self.tiles = []

        for row in range(rows):
            tile_row = []
            for col in range(cols):
                rect = pygame.Rect(
                    x + col * (tile_size + gap),
                    y + row * (tile_size + gap),
                    tile_size,
                    tile_size,
                )
                tile_row.append(Tile(row, col, rect))
            self.tiles.append(tile_row)

    def clear_row(self, row_index):
        for tile in self.tiles[row_index]:
            tile.clear()

    def set_cell(self, row_index, col_index, letter="", is_hint=False):
        tile = self.tiles[row_index][col_index]
        tile.set_data(letter, is_hint)

    def apply_result(self, row_index, result, palette):
        for col in range(len(result)):
            state = result[col]
            self.tiles[row_index][col].start_reveal(state, palette[state])

    def update(self, delta_time, on_reveal=None):
        for row in self.tiles:
            for tile in row:
                tile.update(delta_time, on_reveal)

    def draw(self, screen, font):
        for row in self.tiles:
            for tile in row:
                tile.draw(screen, font)

    def is_animating(self):
        for row in self.tiles:
            for tile in row:
                if tile.revealing:
                    return True
        return False


class Button:
    def __init__(self, rect, text, font):
        self.rect = rect
        self.text = text
        self.font = font

    def draw(self, screen, mouse_pos, enabled=True, selected=False):
        hovered = self.rect.collidepoint(mouse_pos)

        if not enabled:
            color = BUTTON_DISABLED
        elif selected:
            color = BUTTON_SELECTED
        elif hovered:
            color = BUTTON_HOVER
        else:
            color = BUTTON

        shadow_rect = self.rect.move(0, 3)
        pygame.draw.rect(screen, (10, 14, 20), shadow_rect, border_radius=12)
        pygame.draw.rect(screen, color, self.rect, border_radius=12)
        label = self.font.render(self.text, True, WHITE)
        label_rect = label.get_rect(center=self.rect.center)
        screen.blit(label, label_rect)

    def is_clicked(self, event):
        """Обрабатывает клик только при нажатии MOUSEBUTTONDOWN"""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False


# ==================== GAME ====================
class Game:
    WIDTH = 520
    HEIGHT = 760
    FPS = 60
    MAX_ATTEMPTS = 6

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Wordle Style Game - Minecraft Edition")
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        self.clock = pygame.time.Clock()

        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.tile_font = pygame.font.SysFont("arial", 32, bold=True)
        self.ui_font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.tiny_font = pygame.font.SysFont("arial", 16)

        self.word_manager = WordManager()
        self.sound = SoundManager()
        self.palette = {
            "correct": GREEN,
            "present": YELLOW,
            "absent": GRAY,
        }

        self.restart_button = Button(pygame.Rect(18, 690, 118, 48), "Restart", self.ui_font)
        self.menu_button = Button(pygame.Rect(144, 690, 100, 48), "Modes", self.ui_font)
        self.sound_button = Button(pygame.Rect(252, 690, 96, 48), "Sound", self.tiny_font)
        self.hint_button = Button(pygame.Rect(356, 690, 146, 48), "Hint", self.ui_font)
        self.update_sound_button_label()
        self.classic_button = Button(pygame.Rect(50, 225, 190, 56), "Classic Words", self.ui_font)
        self.minecraft_button = Button(pygame.Rect(280, 225, 190, 56), "Minecraft Blocks", self.ui_font)
        self.length_buttons = {
            4: Button(pygame.Rect(70, 360, 80, 52), "4", self.ui_font),
            5: Button(pygame.Rect(170, 360, 80, 52), "5", self.ui_font),
            6: Button(pygame.Rect(270, 360, 80, 52), "6", self.ui_font),
            7: Button(pygame.Rect(370, 360, 80, 52), "7", self.ui_font),
        }
        self.start_button = Button(pygame.Rect(160, 485, 200, 56), "Start Game", self.ui_font)

        self.mode_titles = {
            "classic": "Classic Words",
            "minecraft": "Minecraft Blocks",
        }

        self.current_mode = ""
        self.selected_mode = "classic"
        self.word_length = 5
        self.selected_word_length = 5
        self.secret_word = ""
        self.screen_state = "menu"
        self.message = ""
        self.message_timer = 0.0
        self.game_over = False
        self.player_won = False
        self.current_row = 0
        self.current_guess = ""
        self.current_guess_letters = []
        self.guesses = []
        self.letter_states = {}
        self.hints_used = 0
        self.max_hints = 3
        self.revealed_hints = {}
        self.grid = self.create_grid(5)

    def create_grid(self, word_length):
        tile_sizes = {4: 68, 5: 62, 6: 54, 7: 46}
        gaps = {4: 10, 5: 8, 6: 7, 7: 6}

        tile_size = tile_sizes[word_length]
        gap = gaps[word_length]
        grid_width = word_length * tile_size + (word_length - 1) * gap
        x = (self.WIDTH - grid_width) // 2

        return Grid(x, 120, self.MAX_ATTEMPTS, word_length, tile_size, gap)

    def start_new_game(self, mode=None, word_length=None):
        if mode is not None:
            self.current_mode = mode
            self.selected_mode = mode

        if word_length is not None:
            self.word_length = word_length
            self.selected_word_length = word_length

        if self.current_mode == "":
            self.screen_state = "menu"
            return

        self.secret_word = self.word_manager.choose_word(self.current_mode, self.word_length)
        if os.environ.get("WORDLY_DEBUG", "").lower() in ("1", "true", "yes"):
            print("[DEBUG] Secret word:", self.secret_word)

        self.grid = self.create_grid(self.word_length)
        self.current_row = 0
        self.current_guess = ""
        self.current_guess_letters = [""] * self.word_length
        self.guesses = []
        self.letter_states = {}
        self.message = ""
        self.message_timer = 0.0
        self.game_over = False
        self.player_won = False
        self.hints_used = 0
        self.revealed_hints = {}

        self.max_hints = 2 if self.word_length >= 6 else 3

        self.screen_state = "game"
        self.sync_current_guess()
        self.refresh_current_row()

    def run(self):
        while True:
            delta_time = self.clock.tick(self.FPS) / 1000.0
            self.handle_events()
            self.update(delta_time)
            self.draw()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if self.screen_state == "menu":
                self.handle_menu_events(event)
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.restart_button.is_clicked(event):
                    self.start_new_game()
                    continue

            if self.menu_button.is_clicked(event):
                self.screen_state = "menu"
                self.message = ""
                self.message_timer = 0.0
                continue

            if self.hint_button.is_clicked(event):
                self.use_hint()
                continue

            if self.sound_button.is_clicked(event):
                self.toggle_sound()
                continue

            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

            if self.game_over:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    self.start_new_game()
                continue

            self.handle_keydown(event)

    def handle_menu_events(self, event):
        if self.classic_button.is_clicked(event):
            self.selected_mode = "classic"
            self.ensure_valid_selected_length()
            self.sound.play("click")
            return

        if self.minecraft_button.is_clicked(event):
            self.selected_mode = "minecraft"
            self.ensure_valid_selected_length()
            self.sound.play("click")
            return

        for length in self.length_buttons:
            button = self.length_buttons[length]
            if button.is_clicked(event) and self.is_length_available(self.selected_mode, length):
                self.selected_word_length = length
                self.sound.play("click")
                return

        if self.start_button.is_clicked(event):
            self.sound.play("submit")
            self.try_start_from_menu()
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                self.selected_mode = "classic"
                self.ensure_valid_selected_length()
            elif event.key == pygame.K_2:
                self.selected_mode = "minecraft"
                self.ensure_valid_selected_length()
            elif event.key == pygame.K_4:
                if self.is_length_available(self.selected_mode, 4):
                    self.selected_word_length = 4
            elif event.key == pygame.K_5:
                if self.is_length_available(self.selected_mode, 5):
                    self.selected_word_length = 5
            elif event.key == pygame.K_6:
                if self.is_length_available(self.selected_mode, 6):
                    self.selected_word_length = 6
            elif event.key == pygame.K_7:
                if self.is_length_available(self.selected_mode, 7):
                    self.selected_word_length = 7
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                self.try_start_from_menu()
            elif self.is_sound_toggle_key(event):
                self.toggle_sound()
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

    def try_start_from_menu(self):
        if not self.is_length_available(self.selected_mode, self.selected_word_length):
            self.show_message("This mode does not have words of that length.")
            return

        self.start_new_game(self.selected_mode, self.selected_word_length)

    def ensure_valid_selected_length(self):
        if self.is_length_available(self.selected_mode, self.selected_word_length):
            return

        lengths = self.word_manager.get_available_lengths(self.selected_mode)
        self.selected_word_length = lengths[0]

    def is_length_available(self, mode, word_length):
        lengths = self.word_manager.get_available_lengths(mode)
        return word_length in lengths

    def is_input_locked(self):
        return self.grid.is_animating()

    def update_sound_button_label(self):
        self.sound_button.text = "Sound On" if self.sound.enabled else "Sound Off"

    def toggle_sound(self):
        enabled = self.sound.toggle()
        self.update_sound_button_label()
        self.sound.play("click")
        self.show_message(f"Sound {'on' if enabled else 'off'}")

    def is_sound_toggle_key(self, event):
        if event.type != pygame.KEYDOWN:
            return False
        mods = pygame.key.get_mods()
        if event.key == pygame.K_m and (mods & pygame.KMOD_CTRL):
            return True
        return event.key == pygame.K_BACKQUOTE

    def handle_keydown(self, event):
        if self.is_input_locked():
            self.show_message("Wait for the tiles to finish flipping.")
            return

        if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            self.submit_guess()
            return

        if event.key == pygame.K_BACKSPACE:
            if not self.remove_last_letter():
                self.show_message("Nothing to delete.")
            return

        if self.is_sound_toggle_key(event):
            self.toggle_sound()
            return

        if event.unicode and event.unicode.isalpha():
            if not self.insert_letter(event.unicode.lower()):
                self.show_message(f"Word must be {self.word_length} letters.")
            return

        self.show_message("Use letters, Backspace, Enter, or the Hint button.")

    def insert_letter(self, letter):
        for index in range(self.word_length):
            if self.current_guess_letters[index] == "":
                self.current_guess_letters[index] = letter
                self.sync_current_guess()
                self.refresh_current_row()
                self.sound.play("type")
                return True
        return False

    def remove_last_letter(self):
        for index in range(self.word_length - 1, -1, -1):
            if index in self.revealed_hints:
                continue
            if self.current_guess_letters[index] != "":
                self.current_guess_letters[index] = ""
                self.sync_current_guess()
                self.refresh_current_row()
                self.sound.play("backspace")
                return True
        return False

    def sync_current_guess(self):
        self.current_guess = "".join(self.current_guess_letters).lower()

    def refresh_current_row(self):
        self.grid.clear_row(self.current_row)

        for index in range(self.word_length):
            letter = self.current_guess_letters[index]
            if letter == "":
                continue

            is_hint = index in self.revealed_hints
            self.grid.set_cell(self.current_row, index, letter, is_hint)

    def submit_guess(self):
        if self.is_input_locked():
            self.show_message("Wait for the tiles to finish flipping.")
            return

        self.sync_current_guess()

        if len(self.current_guess) != self.word_length:
            self.show_message(f"Guess must be exactly {self.word_length} letters.")
            self.sound.play("invalid")
            return

        if not self.word_manager.is_valid_word(self.current_guess, self.current_mode, self.word_length):
            self.show_message("Word is not in the dictionary.")
            self.sound.play("invalid")
            return

        self.sound.play("submit")
        result = self.evaluate_guess(self.current_guess, self.secret_word)
        self.grid.apply_result(self.current_row, result, self.palette)
        self.update_letter_states(self.current_guess, result)
        self.guesses.append(self.current_guess)

        if self.current_guess == self.secret_word:
            self.player_won = True
            self.game_over = True
            self.show_message("You guessed the word!")
            self.sound.play("win")
            return

        self.current_row += 1

        if self.current_row >= self.MAX_ATTEMPTS:
            self.player_won = False
            self.game_over = True
            self.show_message(f"The word was {self.secret_word.upper()}.")
            self.sound.play("lose")
            return

        self.current_guess_letters = [""] * self.word_length
        for index in self.revealed_hints:
            self.current_guess_letters[index] = self.revealed_hints[index]
        self.sync_current_guess()
        self.refresh_current_row()

    def evaluate_guess(self, guess, answer):
        result = []
        remaining_letters = list(answer)

        for index in range(self.word_length):
            if guess[index] == answer[index]:
                result.append("correct")
                remaining_letters[index] = None
            else:
                result.append("absent")

        for index in range(self.word_length):
            if result[index] == "correct":
                continue

            letter = guess[index]
            if letter in remaining_letters:
                result[index] = "present"
                remove_index = remaining_letters.index(letter)
                remaining_letters[remove_index] = None

        return result

    def update_letter_states(self, guess, result):
        priority = {
            "absent": 0,
            "present": 1,
            "correct": 2,
        }

        for index in range(len(guess)):
            letter = guess[index]
            state = result[index]

            if letter not in self.letter_states:
                self.letter_states[letter] = state
            else:
                current_state = self.letter_states[letter]
                if priority[state] > priority[current_state]:
                    self.letter_states[letter] = state

    def use_hint(self):
        if self.screen_state != "game":
            return

        if self.game_over:
            return

        if self.is_input_locked():
            self.show_message("Wait for the tiles to finish flipping.")
            return

        if self.hints_used >= self.max_hints:
            self.show_message("No hint charges left.")
            return

        available_positions = []

        for index in range(self.word_length):
            if index in self.revealed_hints:
                continue

            already_correct = False
            for guess in self.guesses:
                if guess[index] == self.secret_word[index]:
                    already_correct = True
                    break

            if not already_correct:
                available_positions.append(index)

        if not available_positions:
            self.show_message("All useful hint positions are already open.")
            return

        reveal_index = random.choice(available_positions)
        reveal_letter = self.secret_word[reveal_index]
        self.revealed_hints[reveal_index] = reveal_letter
        self.current_guess_letters[reveal_index] = reveal_letter
        self.hints_used += 1

        self.sync_current_guess()
        self.refresh_current_row()
        self.sound.play("hint")
        self.show_message(
            f"Hint {self.hints_used}/{self.max_hints}: bulb opened letter {reveal_index + 1}.",
            3.2,
        )

    def show_message(self, message, duration=2.2):
        self.message = message
        self.message_timer = duration

    def update(self, delta_time):
        self.grid.update(delta_time, self.sound.play_reveal)

        if self.message_timer > 0:
            self.message_timer -= delta_time
            if self.message_timer <= 0:
                self.message = ""

    def draw(self):
        self.screen.fill(BG)
        self.draw_background_shapes()

        if self.screen_state == "menu":
            self.draw_menu()
            pygame.display.flip()
            return

        self.draw_header()
        self.grid.draw(self.screen, self.tile_font)
        self.draw_status()
        self.draw_top_panel()

        mouse_pos = pygame.mouse.get_pos()
        self.restart_button.draw(self.screen, mouse_pos)
        self.menu_button.draw(self.screen, mouse_pos)
        self.sound_button.draw(self.screen, mouse_pos, selected=self.sound.enabled)

        hint_enabled = not self.game_over and self.hints_used < self.max_hints
        self.hint_button.draw(self.screen, mouse_pos, enabled=hint_enabled)

        if self.game_over:
            self.draw_game_over()

        pygame.display.flip()

    def draw_header(self):
        title_text = f"{self.mode_titles.get(self.current_mode, '')} {self.word_length} letters"
        title = self.title_font.render(title_text, True, TEXT)
        title_rect = title.get_rect(center=(self.WIDTH // 2, 55))
        self.screen.blit(title, title_rect)

    def draw_menu(self):
        self.draw_panel(pygame.Rect(28, 70, 464, 590))

        title = self.title_font.render("WORDLE STYLE", True, TEXT)
        subtitle = self.ui_font.render("Choose mode and word length", True, TEXT)
        hint = self.small_font.render("1/2 choose mode, 4-7 choose length, Enter starts", True, MUTED_TEXT)

        self.screen.blit(title, title.get_rect(center=(self.WIDTH // 2, 100)))
        self.screen.blit(subtitle, subtitle.get_rect(center=(self.WIDTH // 2, 145)))
        self.screen.blit(hint, hint.get_rect(center=(self.WIDTH // 2, 180)))

        mouse_pos = pygame.mouse.get_pos()
        self.classic_button.draw(self.screen, mouse_pos, selected=self.selected_mode == "classic")
        self.minecraft_button.draw(self.screen, mouse_pos, selected=self.selected_mode == "minecraft")

        length_title = self.ui_font.render("Word Length", True, TEXT)
        self.screen.blit(length_title, length_title.get_rect(center=(self.WIDTH // 2, 320)))

        for length in self.length_buttons:
            button = self.length_buttons[length]
            available = self.is_length_available(self.selected_mode, length)
            selected = self.selected_word_length == length
            button.draw(self.screen, mouse_pos, enabled=available, selected=selected and available)

        start_enabled = self.is_length_available(self.selected_mode, self.selected_word_length)
        self.start_button.draw(self.screen, mouse_pos, enabled=start_enabled)

        available_lengths = self.word_manager.get_available_lengths(self.selected_mode)
        text_lengths = ", ".join(str(length) for length in available_lengths)
        info_text = f"Available lengths for this mode: {text_lengths}"
        info = self.small_font.render(info_text, True, MUTED_TEXT)
        self.screen.blit(info, info.get_rect(center=(self.WIDTH // 2, 435)))

        count_parts = []
        for length in range(4, 8):
            if self.is_length_available(self.selected_mode, length):
                count = len(self.word_manager.get_mode_words(self.selected_mode, length))
                count_parts.append(f"{length}: {count}")
        count_label = self.small_font.render(f"Word counts  {' | '.join(count_parts)}", True, MUTED_TEXT)
        self.screen.blit(count_label, count_label.get_rect(center=(self.WIDTH // 2, 560)))

        if self.message:
            message_label = self.small_font.render(self.message, True, TEXT)
            self.screen.blit(message_label, message_label.get_rect(center=(self.WIDTH // 2, 620)))

    def draw_top_panel(self):
        self.draw_panel(pygame.Rect(12, 12, 496, 94))

        mode_text = self.mode_titles.get(self.current_mode, "")
        mode_label = self.small_font.render(mode_text, True, MUTED_TEXT)
        self.screen.blit(mode_label, (24, 24))

        length_label = self.small_font.render(f"{self.word_length} letters", True, MUTED_TEXT)
        self.screen.blit(length_label, (24, 44))

        attempt_num = min(self.current_row + 1, self.MAX_ATTEMPTS)
        attempt_text = f"Attempt {attempt_num}/{self.MAX_ATTEMPTS}"
        attempt_label = self.small_font.render(attempt_text, True, MUTED_TEXT)
        attempt_rect = attempt_label.get_rect(topright=(self.WIDTH - 24, 44))
        self.screen.blit(attempt_label, attempt_rect)

        hint_text = f"Hints {self.hints_used}/{self.max_hints}"
        hint_label = self.small_font.render(hint_text, True, MUTED_TEXT)
        hint_rect = hint_label.get_rect(topright=(self.WIDTH - 24, 24))
        self.screen.blit(hint_label, hint_rect)

    def draw_status(self):
        self.draw_panel(pygame.Rect(58, 548, 404, 88))

        guess_label = self.small_font.render(f"Current: {self.current_guess.upper()}", True, TEXT)
        guess_rect = guess_label.get_rect(center=(self.WIDTH // 2, 570))
        self.screen.blit(guess_label, guess_rect)

        helper_text = f"Hints: {self.hints_used}/{self.max_hints}   Ctrl+M or ` toggles sound"
        helper_label = self.tiny_font.render(helper_text, True, MUTED_TEXT)
        helper_rect = helper_label.get_rect(center=(self.WIDTH // 2, 594))
        self.screen.blit(helper_label, helper_rect)

        if self.message:
            message_label = self.small_font.render(self.message, True, TEXT)
            message_rect = message_label.get_rect(center=(self.WIDTH // 2, 618))
            self.screen.blit(message_label, message_rect)

        key_x = 44
        key_y = 648
        letters = sorted(self.letter_states.keys())

        for letter in letters:
            state = self.letter_states[letter]
            badge = pygame.Rect(key_x, key_y, 28, 28)
            pygame.draw.rect(self.screen, self.palette[state], badge, border_radius=6)
            glyph = self.small_font.render(letter.upper(), True, TEXT)
            glyph_rect = glyph.get_rect(center=badge.center)
            self.screen.blit(glyph, glyph_rect)

            key_x += 34
            if key_x > self.WIDTH - 44:
                key_x = 44
                key_y += 34

    def draw_panel(self, rect):
        shadow_rect = rect.move(0, 4)
        pygame.draw.rect(self.screen, (9, 12, 18), shadow_rect, border_radius=18)
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=18)
        pygame.draw.rect(self.screen, (57, 67, 83), rect, width=1, border_radius=18)

    def draw_background_shapes(self):
        background_layer = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(background_layer, (26, 40, 64, 85), (72, 72), 70)
        pygame.draw.circle(background_layer, (20, 52, 66, 70), (470, 110), 92)
        pygame.draw.circle(background_layer, (34, 38, 58, 65), (430, 720), 120)
        self.screen.blit(background_layer, (0, 0))

    def draw_game_over(self):
        overlay = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(70, 225, 380, 210)
        pygame.draw.rect(self.screen, (32, 32, 34), panel, border_radius=14)
        pygame.draw.rect(self.screen, (90, 90, 95), panel, width=2, border_radius=14)

        title_text = "You Win!" if self.player_won else "Game Over"
        title_label = self.title_font.render(title_text, True, TEXT)
        title_rect = title_label.get_rect(center=(self.WIDTH // 2, 265))
        self.screen.blit(title_label, title_rect)

        if self.player_won:
            tries_used = len(self.guesses)
            stats_text = f"Solved in {tries_used}/{self.MAX_ATTEMPTS} tries"
        else:
            stats_text = f"Used all {self.MAX_ATTEMPTS} attempts"
        stats_label = self.ui_font.render(stats_text, True, MUTED_TEXT)
        stats_rect = stats_label.get_rect(center=(self.WIDTH // 2, 310))
        self.screen.blit(stats_label, stats_rect)

        word_label = self.ui_font.render(f"Word: {self.secret_word.upper()}", True, TEXT)
        word_rect = word_label.get_rect(center=(self.WIDTH // 2, 350))
        self.screen.blit(word_label, word_rect)

        hint_label = self.small_font.render("Press Enter or click Restart", True, TEXT)
        hint_rect = hint_label.get_rect(center=(self.WIDTH // 2, 400))
        self.screen.blit(hint_label, hint_rect)


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()