from argparse import ArgumentParser, Namespace
from spotty.providers.vast.helpers.vast_cli import search__offers, deindent, api_key_guard, api_key_file_base, \
    server_url_default
from spotty.providers.vast.helpers.vast_cli import parser as vast_parser

from spotty.commands.abstract_command import AbstractCommand
from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter


class SearchOfferCommand(AbstractCommand):
    name = 'search-offers'
    description = 'Search for Instance Types'

    def configure(self, parser: ArgumentParser):
        super().configure(parser)
        parser.add_argument("--url", help="server REST api url", default=server_url_default)
        parser.add_argument("--raw", action="store_true", help="output machine-readable json")
        parser.add_argument("--api-key",
                            help="api key. defaults to using the one stored in {}".format(api_key_file_base), type=str,
                            required=False, default="")
        parser.add_argument("-t", "--type", default="on-demand",
                            help="Show 'bid'(interruptible) or 'on-demand' offers. default: on-demand")
        parser.add_argument("-i", "--interruptible", dest="type", const="bid", action="store_const",
                            help="Alias for --type=bid")
        parser.add_argument("-b", "--bid", dest="type", const="bid", action="store_const", help="Alias for --type=bid")
        parser.add_argument("--on-demand", dest="type", const="on-demand", action="store_const",
                            help="Alias for --type=on-demand")
        parser.add_argument("-n", "--no-default", action="store_true", help="Disable default query")
        parser.add_argument("--disable-bundling", action="store_true",
                            help="Show identical offers. This request is more heavily rate limited.")
        parser.add_argument("--storage", type=float, default=5.0,
                            help="Amount of storage to use for pricing, in GiB. default=5.0GiB")
        parser.add_argument("-o", "--order", type=str,
                            help="Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-'",
                            default='score-')
        parser.add_argument("query",
                            nargs="*", default=None,
                            help="""
        Query to search for. default: 'external=false rentable=true verified=true', pass -n to ignore default
        Query syntax:

            query = comparison comparison...
            comparison = field op value
            field = <name of a field>
            op = one of: <, <=, ==, !=, >=, >, in, notin
            value = <bool, int, float, etc> | 'any'

        note: to pass '>' and '<' on the command line, make sure to use quotes
        note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'


        Examples:

            spotty vast search-offers 'compute_cap > 610 total_flops < 5 datacenter=true'
            spotty vast search-offers 'reliability > 0.99  num_gpus>=4 verified=false' -o 'num_gpus-'
            spotty vast search-offers 'rentable = any'
            spotty vast search-offers 'reliability > 0.98 num_gpus=1 gpu_name=RTX_3090'

        Available fields:

              Name                  Type       Description

            bw_nvlink               float     bandwidth NVLink
            compute_cap:            int       cuda compute capability*100  (ie:  650 for 6.5, 700 for 7.0)
            cpu_cores:              int       # virtual cpus
            cpu_cores_effective:    float     # virtual cpus you get
            cpu_ram:                float     system RAM in gigabytes
            cuda_vers:              float     cuda version
            datacenter:             bool      show only datacenter offers
            direct_port_count       int       open ports on host's router
            disk_bw:                float     disk read bandwidth, in MB/s
            disk_space:             float     disk storage space, in GB
            dlperf:                 float     DL-perf score  (see FAQ for explanation)
            dlperf_usd:             float     DL-perf/$
            dph:                    float     $/hour rental cost
            driver_version          string    driver version in use on a host.
            duration:               float     max rental duration in days
            external:               bool      show external offers in addition to datacenter offers
            flops_usd:              float     TFLOPs/$
            gpu_mem_bw:             float     GPU memory bandwidth in GB/s
            gpu_name:               string    GPU model name (no quotes, replace spaces with underscores, ie: RTX_3090 rather than 'RTX 3090')
            gpu_ram:                float     GPU RAM in GB
            gpu_frac:               float     Ratio of GPUs in the offer to gpus in the system
            gpu_display_active:     bool      True if the GPU has a display attached
            has_avx:                bool      CPU supports AVX instruction set.
            id:                     int       instance unique ID
            inet_down:              float     internet download speed in Mb/s
            inet_down_cost:         float     internet download bandwidth cost in $/GB
            inet_up:                float     internet upload speed in Mb/s
            inet_up_cost:           float     internet upload bandwidth cost in $/GB
            machine_id              int       machine id of instance
            min_bid:                float     current minimum bid price in $/hr for interruptible
            num_gpus:               int       # of GPUs
            pci_gen:                float     PCIE generation
            pcie_bw:                float     PCIE bandwidth (CPU to GPU)
            reliability:            float     machine reliability score (see FAQ for explanation)
            rentable:               bool      is the instance currently rentable
            rented:                 bool      is the instance currently rented
            storage_cost:           float     storage cost in $/GB/month
            total_flops:            float     total TFLOPs from all GPUs
            verified:               bool      is the machine verified
    """)

    def run(self, args: Namespace, output: AbstractOutputWriter):
        search__offers(args)
