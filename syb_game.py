"""SYB Network - Game Mode (Simple Print-Based UI)

A simple, game-like interface that uses print statements and runs in a loop.
No complex widgets - just straightforward output that works everywhere.
"""

import time
import random
import asyncio
from contract_interface import SYBContract, SYBUser
from network import Network
from utils import (
    generate_mul_eth_addresses,
    format_transaction_display,
    generate_random_eth_address
)
import datetime
import matplotlib.pyplot as plt
import networkx as nx
from IPython.display import clear_output, display


def create_random_network(num_users=8, random_name='erdos_renyi', balance_range=(0.0, 0.1)) -> tuple:
    """Create a random network, initialize contract, and set up user interfaces."""
    print(f"📊 Creating '{random_name}' network with {num_users} users...")
    network = Network.init_random(n_nodes=num_users, random_name=random_name, balance_range=balance_range)
    contract = SYBContract(scoring_algorithm='pagerank')
    contract.network = network

    initial_addresses = generate_mul_eth_addresses(num_users)
    user_names = [f"User {i}" for i in range(num_users)]

    print("\n💰 Funding user accounts from network balances...")
    for i, addr in enumerate(initial_addresses):
        balance_eth = network.balance_list[i]
        deposit_amount = int(balance_eth * 10**18)
        contract.deposit(addr, deposit_amount)

    print("\n🤝 Creating vouching network from existing graph...")
    for u, v in network.graph.edges():
        addr1, addr2 = initial_addresses[u], initial_addresses[v]
        contract.vouch(addr1, addr2)

    print("\n⚡ Processing initial batch to establish scores...")
    try:
        contract.forge_batch()
        print("✅ Initial batch processed successfully!")
    except Exception as e:
        print(f"⚠️ Initial batch processing failed: {e}")

    users = {}
    for i, addr in enumerate(initial_addresses):
        users[addr] = {
            'interface': SYBUser(contract, addr),
            'name': user_names[i],
            'address': addr
        }

    return contract, users


class SYBGame:
    """Game-like simulation using simple prints."""

    def __init__(self, contract: SYBContract, users: dict, interval: int = 10, show_graph: bool = True):
        """
        Initialize the game.

        Args:
            contract: SYBContract instance
            users: Dictionary of user information
            interval: Seconds between automatic transactions (default: 10)
            show_graph: Whether to show matplotlib graph (default: True)
        """
        self.contract = contract
        self.users = users
        self.interval = interval
        self.running = False
        self.next_user_id = len(users)
        self.auto_show_graph = show_graph  # Renamed to avoid conflict with method
        self.graph_pos = None  # Cache graph layout

        # Get first user as the connected user
        self.first_user_addr = list(users.keys())[0]
        self.first_user = users[self.first_user_addr]

    def _timestamp(self):
        """Get current timestamp."""
        return datetime.datetime.now().strftime("%H:%M:%S")

    def _print_header(self):
        """Print game header."""
        print("\n" + "="*60)
        print("🎮 SYB NETWORK - GAME MODE")
        print("="*60)
        print(f"👤 Connected as: {self.first_user['name']}")
        print(f"⏱️  Auto-transaction interval: {self.interval} seconds")
        print(f"📊 Batch size: {self.contract.batch_size} transactions")
        print(f"🌐 Network: {self.contract.network.graph.number_of_nodes()} nodes, {self.contract.network.graph.number_of_edges()} edges")
        print("="*60 + "\n")

    def _print_status(self):
        """Print current status."""
        queue_size = len(self.contract.unprocessed_txns)
        last_batch = self.contract.last_forged_batch
        total_users = len(self.users)

        # Calculate total balance
        total_balance = sum(u['interface'].get_my_balance() / 10**18 for u in self.users.values())

        print(f"[{self._timestamp()}] 📊 Status: Queue={queue_size}/{self.contract.batch_size} | Batch=#{last_batch} | Users={total_users} | Total={total_balance:.2f} ETH")

    def _draw_ascii_graph(self):
        """Draw a simple ASCII representation of the network."""
        print(f"\n[{self._timestamp()}] 🌐 Network Graph (ASCII):")
        print("─" * 60)

        G = self.contract.network.graph
        scores = self.contract.network.compute_score('pagerank')

        # Show nodes with their connections
        for node in sorted(G.nodes()):
            addr = self.contract.idx_to_address.get(node)
            user_name = self.users.get(addr, {}).get('name', f'Node {node}')
            balance = self.contract.network.balance_list[node] if node < len(self.contract.network.balance_list) else 0
            score = scores[node] if node < len(scores) else 0

            # Get neighbors
            neighbors = list(G.neighbors(node))
            neighbor_names = [self.users.get(self.contract.idx_to_address.get(n), {}).get('name', f'N{n}') for n in neighbors]

            # Create bar for score (scaled 0-20 characters)
            bar_length = int(score * 100)  # Scale score to 0-20
            bar = "█" * min(bar_length, 20)

            print(f"  {user_name:8} [{score:5.3f}] {bar:20} | {balance:.2f} ETH | → {', '.join(neighbor_names) if neighbor_names else 'none'}")

        print("─" * 60)

    def _draw_matplotlib_graph(self):
        """Draw network graph using matplotlib."""
        try:
            G = self.contract.network.graph

            if G.number_of_nodes() == 0:
                print(f"[{self._timestamp()}] ⚠️ Empty network, skipping graph")
                return

            # Compute scores
            scores = self.contract.network.compute_score('pagerank')

            # Use cached layout or create new one
            if self.graph_pos is None:
                self.graph_pos = nx.spring_layout(G, seed=42)

            # Create figure
            plt.figure(figsize=(10, 6))

            # Prepare node colors (scores) and sizes (balances)
            node_colors = []
            node_sizes = []
            node_labels = {}

            for node in G.nodes():
                addr = self.contract.idx_to_address.get(node)
                user_name = self.users.get(addr, {}).get('name', f'N{node}')
                balance = self.contract.network.balance_list[node] if node < len(self.contract.network.balance_list) else 0
                score = scores[node] if node < len(scores) else 0

                node_colors.append(score)
                node_sizes.append(max(300, balance * 3000))
                node_labels[node] = f"{user_name}\n{score:.3f}"

            # Draw edges
            nx.draw_networkx_edges(G, self.graph_pos, alpha=0.3, width=2)

            # Draw nodes
            nodes = nx.draw_networkx_nodes(
                G, self.graph_pos,
                node_color=node_colors,
                node_size=node_sizes,
                cmap=plt.cm.viridis,
                vmin=0,
                vmax=max(node_colors) if node_colors else 1,
                alpha=0.9
            )

            # Draw labels
            nx.draw_networkx_labels(G, self.graph_pos, node_labels, font_size=8, font_weight='bold')

            # Add colorbar
            if nodes:
                plt.colorbar(nodes, label='Score (PageRank)')

            plt.title(f"SYB Network - Batch #{self.contract.last_forged_batch} | {G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
                     fontsize=14, fontweight='bold')
            plt.axis('off')
            plt.tight_layout()

            # Display without clearing output (shows history of graphs)
            print(f"[{self._timestamp()}] 📊 Network Visualization (Batch #{self.contract.last_forged_batch}):")
            plt.show()
            plt.close()

        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Graph drawing error: {e}")

    def _simulate_transaction(self):
        """Generate a random transaction."""
        try:
            # Get random user (not the connected user)
            other_users = [(addr, data) for addr, data in self.users.items()
                          if addr != self.first_user_addr]

            if not other_users:
                return

            user_addr, user_data = random.choice(other_users)
            user_interface = user_data['interface']
            txn_type = random.choice(['deposit', 'withdraw', 'vouch', 'unvouch'])

            if txn_type == 'deposit':
                amount = random.uniform(0.1, 2.0)
                user_interface.deposit(int(amount * 10**18))
                print(f"[{self._timestamp()}] 💰 {user_data['name']} deposited {amount:.2f} ETH")

            elif txn_type == 'withdraw':
                balance = user_interface.get_my_balance()
                if balance > 0:
                    max_withdraw = balance * 0.5
                    amount = random.uniform(0.1 * 10**18, min(max_withdraw, 1.0 * 10**18))
                    user_interface.withdraw(int(amount))
                    print(f"[{self._timestamp()}] 💸 {user_data['name']} withdrew {amount/10**18:.2f} ETH")

            elif txn_type == 'vouch':
                possible_targets = [addr for addr in self.users.keys()
                                  if addr != user_addr and addr != self.first_user_addr]
                if possible_targets:
                    target = random.choice(possible_targets)
                    vouches = self.contract.vouches.get(user_addr, {})
                    if not vouches.get(target, False):
                        user_interface.vouch(target)
                        print(f"[{self._timestamp()}] 👍 {user_data['name']} vouched for {self.users[target]['name']}")

            elif txn_type == 'unvouch':
                vouches = self.contract.vouches.get(user_addr, {})
                active_vouches = [addr for addr, is_vouched in vouches.items() if is_vouched]
                if active_vouches:
                    target = random.choice(active_vouches)
                    user_interface.unvouch(target)
                    print(f"[{self._timestamp()}] 👎 {user_data['name']} unvouched {self.users[target]['name']}")

        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Simulation error: {e}")

    def _check_and_forge(self):
        """Check if batch should be forged and do it."""
        queue_size = len(self.contract.unprocessed_txns)

        if queue_size >= self.contract.batch_size:
            print(f"\n[{self._timestamp()}] ⚡ Queue full ({queue_size}/{self.contract.batch_size})! Forging batch...")

            try:
                result = self.contract.forge_batch()
                if result:
                    batch_num = self.contract.last_forged_batch
                    num_txns = len(result.transactions_processed)
                    print(f"[{self._timestamp()}] ✅ Batch #{batch_num} forged successfully! Processed {num_txns} transactions")

                    # Show some score changes
                    print(f"[{self._timestamp()}] 📈 Score updates:")
                    for i, (addr, user_data) in enumerate(list(self.users.items())[:3]):
                        score = user_data['interface'].get_my_score()
                        print(f"    • {user_data['name']}: {score:.4f}")
                    print()

                    # Show ASCII graph after batch forge
                    self._draw_ascii_graph()

                    # Show matplotlib graph if enabled
                    if self.auto_show_graph:
                        self._draw_matplotlib_graph()

                else:
                    print(f"[{self._timestamp()}] ⚠️ Batch forging returned no result")

            except Exception as e:
                print(f"[{self._timestamp()}] ❌ Batch forging failed: {e}")

    async def run(self):
        """Run the game loop."""
        self.running = True
        self._print_header()

        print(f"[{self._timestamp()}] 🎬 Game started! Automatic transactions every {self.interval} seconds")
        print(f"[{self._timestamp()}] 💡 The game runs automatically. Watch the transactions happen!\n")

        tick = 0
        try:
            while self.running:
                tick += 1

                # Every tick, simulate a transaction
                self._simulate_transaction()

                # Check if we need to forge
                self._check_and_forge()

                # Show status every tick
                self._print_status()

                # Wait for next tick
                await asyncio.sleep(self.interval)

        except asyncio.CancelledError:
            print(f"\n[{self._timestamp()}] ⏸️ Game stopped")
            self.running = False

    def stop(self):
        """Stop the game."""
        self.running = False
        print(f"\n[{self._timestamp()}] 🛑 Game stopped by user")

    # Manual actions for the connected user
    def deposit(self, amount_eth: float):
        """Deposit ETH (as connected user)."""
        try:
            amount = int(amount_eth * 10**18)
            self.first_user['interface'].deposit(amount)
            print(f"[{self._timestamp()}] 💰 YOU deposited {amount_eth:.2f} ETH")
            self._check_and_forge()
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Deposit failed: {e}")

    def withdraw(self, amount_eth: float):
        """Withdraw ETH (as connected user)."""
        try:
            amount = int(amount_eth * 10**18)
            self.first_user['interface'].withdraw(amount)
            print(f"[{self._timestamp()}] 💸 YOU withdrew {amount_eth:.2f} ETH")
            self._check_and_forge()
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Withdraw failed: {e}")

    def vouch(self, user_name: str):
        """Vouch for another user (as connected user)."""
        try:
            # Find user by name
            target_addr = None
            for addr, data in self.users.items():
                if data['name'] == user_name:
                    target_addr = addr
                    break

            if target_addr:
                self.first_user['interface'].vouch(target_addr)
                print(f"[{self._timestamp()}] 👍 YOU vouched for {user_name}")
                self._check_and_forge()
            else:
                print(f"[{self._timestamp()}] ❌ User '{user_name}' not found")
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Vouch failed: {e}")

    def unvouch(self, user_name: str):
        """Unvouch a user (as connected user)."""
        try:
            # Find user by name
            target_addr = None
            for addr, data in self.users.items():
                if data['name'] == user_name:
                    target_addr = addr
                    break

            if target_addr:
                self.first_user['interface'].unvouch(target_addr)
                print(f"[{self._timestamp()}] 👎 YOU unvouched {user_name}")
                self._check_and_forge()
            else:
                print(f"[{self._timestamp()}] ❌ User '{user_name}' not found")
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Unvouch failed: {e}")

    def create_user(self):
        """Create a new user."""
        try:
            new_addr = generate_random_eth_address()
            user_name = f"User {self.next_user_id}"
            initial_deposit = random.uniform(0.5, 3.0)

            self.contract.deposit(new_addr, int(initial_deposit * 10**18))
            user_interface = SYBUser(self.contract, new_addr)

            self.users[new_addr] = {
                'interface': user_interface,
                'name': user_name,
                'address': new_addr
            }

            self.next_user_id += 1
            print(f"[{self._timestamp()}] 👤 Created {user_name} with {initial_deposit:.2f} ETH")
            self._check_and_forge()
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ User creation failed: {e}")

    def my_balance(self):
        """Check your balance."""
        try:
            balance = self.first_user['interface'].get_my_balance() / 10**18
            score = self.first_user['interface'].get_my_score()
            print(f"[{self._timestamp()}] 💰 YOUR balance: {balance:.4f} ETH | Score: {score:.4f}")
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error: {e}")

    def list_users(self):
        """List all users."""
        print(f"\n[{self._timestamp()}] 👥 Network Users:")
        for addr, data in self.users.items():
            balance = data['interface'].get_my_balance() / 10**18
            score = data['interface'].get_my_score()
            marker = "👉 " if addr == self.first_user_addr else "   "
            print(f"{marker}{data['name']}: {balance:.2f} ETH | Score: {score:.4f}")
        print()

    def show_queue(self):
        """Show current transaction queue."""
        txns = self.contract.unprocessed_txns
        print(f"\n[{self._timestamp()}] 📋 Transaction Queue ({len(txns)}/{self.contract.batch_size}):")
        if not txns:
            print("   Queue is empty")
        else:
            for i, txn in enumerate(txns[:10], 1):
                txn_str = format_transaction_display(txn, self.users, index=i)
                print(f"   {txn_str}")
            if len(txns) > 10:
                print(f"   ... and {len(txns) - 10} more")
        print()

    def show_graph_ascii(self):
        """Show ASCII graph of network."""
        self._draw_ascii_graph()

    def show_graph(self):
        """Show matplotlib graph of network."""
        self._draw_matplotlib_graph()

    def toggle_graph(self, enabled: bool = None):
        """Toggle automatic graph display after batch forging."""
        if enabled is None:
            self.auto_show_graph = not self.auto_show_graph
        else:
            self.auto_show_graph = enabled
        print(f"[{self._timestamp()}] 📊 Automatic graph display: {'ON' if self.auto_show_graph else 'OFF'}")


# Convenience function to start a game
async def start_game(contract, users, interval=10, show_graph=True):
    """
    Start the game and return the game instance.

    Args:
        contract: SYBContract instance
        users: Dictionary of user information
        interval: Seconds between automatic transactions
        show_graph: Whether to show matplotlib graphs after batch forging

    Returns:
        game: SYBGame instance
        task: Asyncio task running the game
    """
    game = SYBGame(contract, users, interval, show_graph)

    # Show initial graph
    print("\n" + "="*60)
    print("🎨 INITIAL NETWORK STATE")
    print("="*60)
    game.show_graph_ascii()
    if show_graph:
        game.show_graph()

    # Start the game in the background
    task = asyncio.create_task(game.run())

    # Give it a moment to start
    await asyncio.sleep(0.1)

    return game, task
