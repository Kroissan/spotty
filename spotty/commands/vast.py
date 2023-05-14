from spotty.commands.abstract_provider_command import AbstractProviderCommand
from spotty.providers.vast.commands.search_offers import SearchOfferCommand
from spotty.providers.vast.commands.set_api_key import SetApiKey


class VastCommand(AbstractProviderCommand):

    name = 'vast'
    description = 'Vast.ai related commands.'
    commands = [
        SearchOfferCommand,
        SetApiKey,
    ]
