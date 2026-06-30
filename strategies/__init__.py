from strategies.add_torrent import AddTorrentStrategy
from strategies.base import BotStrategy
from strategies.restart_server import RestartServerStrategy

STRATEGIES: list[BotStrategy] = [
    AddTorrentStrategy(),
    RestartServerStrategy(),
]

STRATEGY_BY_CALLBACK: dict[str, BotStrategy] = {
    strategy.callback_data: strategy for strategy in STRATEGIES
}


def collect_conversation_states() -> dict[int, list]:
    states: dict[int, list] = {}
    for strategy in STRATEGIES:
        states.update(strategy.conversation_states())
    return states
