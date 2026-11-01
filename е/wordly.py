import json
import random
import re
from pathlib import Path

import pygame

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "blocks.json").exists() else SCRIPT_DIR.parent
WIDTH, HEIGHT = 800, 600
MAX_TRIES = 5
MINECRAFT_LENGTHS = (4, 5, 6, 7)

WHITE = (245, 245, 245)
BLACK = (20, 20, 20)
GRAY = (170, 170, 170)
DARK_GRAY = (80, 80, 80)
GREEN = (65, 160, 90)
YELLOW = (210, 170, 50)
PURPLE = (125, 70, 220)


def clean_word(value):
    return re.sub(r"[^a-z]", "", str(value).lower())
    #Master Degree! --> masterdegree



def unique_entries(entries):
    seen = set()
    result = []
    for word, label in entries:
        if word and word not in seen:
            seen.add(word)
            result.append({"word": word, "label": label})
    return result


def load_words():
    with open(ROOT / "blocks.json", "r", encoding="utf-8") as file:
        blocks = json.load(file)
    with open(ROOT / "words.json", "r", encoding="utf-8") as file:
        words_data = json.load(file)

    lists = {"minecraft": {}, "regular": {}}

    for length in MINECRAFT_LENGTHS:
        entries = []
        for block in blocks:
            label = block.get("displayName") or block.get("name") or ""
            word = clean_word(label)
            if len(word) == length:
                entries.append((word, label))
        lists["minecraft"][length] = unique_entries(entries)

    regular = []
    for word in words_data.get("words", []):
        word = clean_word(word)
        if len(word) == 5:
            regular.append((word, word.upper()))
    lists["regular"][5] = unique_entries(regular)

    return lists


class Button:
    def __init__(self, rect, text, action):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.active = False
        self.disabled = False

    def draw(self, screen, font):
        if self.disabled:
            bg = (225, 225, 225)
            fg = GRAY
        elif self.active:
            bg = BLACK
            fg = WHITE
        else:
            bg = WHITE
            fg = BLACK

        pygame.draw.rect(screen, bg, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 2)
        text = font.render(self.text, True, fg)
        
        screen.blit(text, text.get_rect(center=self.rect.center))

    def click(self, pos):
        if not self.disabled and self.rect.collidepoint(pos):
            self.action()
            return True
        return False


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("WORDLY")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.title_font = pygame.font.SysFont("arial", 42, bold=True)
        self.tile_font = pygame.font.SysFont("arial", 32, bold=True)

        self.word_lists = load_words()
        self.mode = "minecraft"
        self.length = 5
        self.answer = None
        self.guesses = []
        self.current_guess = ""
        self.revealed = set()
        self.hints_used = 0
        self.finished = False
        self.message = ""
        self.buttons = []
        self.start_time = 0
        self.elapsed_time = 0

        self.new_game()

    def new_game(self):
        self.answer = random.choice(self.word_lists[self.mode][self.length])
        print(f"Answer: {self.answer['word']} ({self.answer['label']})")
        self.guesses = []
        self.current_guess = ""
        self.revealed = set()
        self.hints_used = 0
        self.finished = False
        self.message = f"{self.mode.title()} mode, {self.length} letters"
        self.start_time = pygame.time.get_ticks()
        self.elapsed_time = 0
        print("Minecraft letter count: ", len(self.word_lists[self.mode][self.length]))
        self.make_buttons()

    def make_buttons(self):
        self.buttons = [
            Button((40, 80, 120, 35), "Minecraft", lambda: self.set_mode("minecraft")),
            Button((170, 80, 100, 35), "Regular", lambda: self.set_mode("regular")),
            Button((40, 530, 120, 35), "New Game", self.new_game),
            Button((640, 80, 100, 35), "Hint", self.use_hint),
        ]

        x = 40
        for length in MINECRAFT_LENGTHS:
            self.buttons.append(Button((x, 130, 45, 32), str(length), lambda value=length: self.set_length(value)))
            x += 55

        self.update_buttons()

    def update_buttons(self):
        for button in self.buttons:
            button.active = False
            button.disabled = False
            if button.text == "Minecraft":
                button.active = self.mode == "minecraft"
            elif button.text == "Regular":
                button.active = self.mode == "regular"
            elif button.text in {"4", "5", "6", "7"}:
                button.active = self.mode == "minecraft" and int(button.text) == self.length
                button.disabled = self.mode == "regular"
            elif button.text == "Hint":
                button.disabled = self.finished or self.hints_used >= 3

    def set_mode(self, mode):
        self.mode = mode
        if mode == "regular":
            self.length = 5
        self.new_game()

    def set_length(self, length):
        if self.mode == "minecraft":
            self.length = length
            self.new_game()

    def use_hint(self):
        if self.finished or self.hints_used >= 3:
            return
        choices = [i for i in range(self.length) if i not in self.revealed]
        if not choices:
            return
        index = random.choice(choices)
        self.revealed.add(index)
        self.hints_used += 1
        self.current_guess = self.with_revealed(self.current_guess)
        self.message = f"Hint used: letter {index + 1} revealed"
        self.update_buttons()

    def with_revealed(self, guess):
        chars = list(guess.ljust(self.length)[: self.length])
        for index in self.revealed:
            chars[index] = self.answer["word"][index]
        return "".join(chars).rstrip()

    def add_letter(self, letter):
        chars = list(self.with_revealed(self.current_guess).ljust(self.length))
        for index in range(self.length):
            if index not in self.revealed and chars[index] == " ":
                chars[index] = letter
                self.current_guess = "".join(chars).rstrip()
                return

    def backspace(self):
        chars = list(self.with_revealed(self.current_guess).ljust(self.length))
        for index in range(self.length - 1, -1, -1):
            if index not in self.revealed and chars[index] != " ":
                chars[index] = " "
                self.current_guess = "".join(chars).rstrip()
                return

    def submit(self):
        guess = self.with_revealed(self.current_guess)
        if len(guess) != self.length or " " in guess:
            self.message = f"Type {self.length} letters"
            return

        allowed = {entry["word"] for entry in self.word_lists[self.mode][self.length]}
        if guess not in allowed:
            self.message = "Word not in this mode"
            return

        self.guesses.append(guess)
        self.current_guess = ""

        if guess == self.answer["word"]:
            self.finished = True
            self.message = f"You won. Answer: {self.answer['label']}"
        elif len(self.guesses) == MAX_TRIES:
            self.finished = True
            self.message = f"You lost. Answer: {self.answer['label']}"
        else:
            self.message = f"{MAX_TRIES - len(self.guesses)} tries left"

        self.update_buttons()

    def score(self, guess):
        answer = self.answer["word"]
        result = ["miss"] * len(guess)
        remaining = {}

        for i, letter in enumerate(answer):
            if guess[i] == letter:
                result[i] = "hit"
            else:
                remaining[letter] = remaining.get(letter, 0) + 1

        for i, letter in enumerate(guess):
            if result[i] == "hit":
                continue
            if remaining.get(letter, 0):
                result[i] = "near"
                remaining[letter] -= 1

        return result

    def handle_key(self, event):
        if self.finished:
            if event.key == pygame.K_RETURN:
                self.new_game()
            return

        if event.key == pygame.K_RETURN:
            self.submit()
        elif event.key == pygame.K_BACKSPACE:
            self.backspace()
        elif event.unicode and event.unicode.isalpha():
            self.add_letter(event.unicode.lower())

    def draw(self):
        self.screen.fill(WHITE)

        self.screen.blit(self.title_font.render("WORDLY", True, BLACK), (40, 25))
        self.screen.blit(self.small_font.render(self.message, True, DARK_GRAY), (40, 175))
        self.screen.blit(self.small_font.render(f"Hints: {3 - self.hints_used}", True, DARK_GRAY), (650, 120))

        for button in self.buttons:
            button.draw(self.screen, self.small_font)

        self.draw_board()
        self.draw_help()
        if not self.finished:
            self.elapsed_time = (
                pygame.time.get_ticks() - self.start_time
            ) // 1000

        timer_text = self.small_font.render(
            f"Time: {self.elapsed_time}s",
            True,YELLOW
            
        )

        self.screen.blit(timer_text, (650, 150))
        pygame.display.flip()

    def draw_board(self):
        tile = 55
        gap = 8
        board_width = self.length * tile + (self.length - 1) * gap
        start_x = WIDTH // 2 - board_width // 2
        start_y = 220

        for row in range(MAX_TRIES):
            if row < len(self.guesses):
                guess = self.guesses[row]
                marks = self.score(guess)
            elif row == len(self.guesses) and not self.finished:
                guess = self.with_revealed(self.current_guess)
                marks = []
            else:
                guess = ""
                marks = []

            for col in range(self.length):
                rect = pygame.Rect(start_x + col * (tile + gap), start_y + row * (tile + gap), tile, tile)
                letter = guess[col].upper() if col < len(guess) else ""

                if marks:
                    if marks[col] == "hit":
                        color = GREEN
                    elif marks[col] == "near":
                        color = YELLOW
                    else:
                        color = GRAY
                elif row == len(self.guesses) and col in self.revealed and not self.finished:
                    color = PURPLE
                else:
                    color = WHITE

                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, BLACK, rect, 2)
                text_color = WHITE if color in {GREEN, PURPLE, GRAY} else BLACK
                text = self.tile_font.render(letter, True, text_color)
                self.screen.blit(text, text.get_rect(center=rect.center))

    def draw_help(self):
        lines = [
            "Type letters, Enter to guess, Backspace to erase.",
            "Green = right place, Yellow = wrong place, Gray = not in word.",
        ]
        y = 555
        for line in lines:
            self.screen.blit(self.small_font.render(line, True, DARK_GRAY), (210, y))
            y += 20

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for button in self.buttons:
                        if button.click(event.pos):
                            break
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event)

            self.draw()

        pygame.quit()


if __name__ == "__main__":
    Game().run()
