"""SYB Network User Interface - Plotly Version (Binder-Friendly)

This version uses Plotly for interactive graphs and simplified ipywidgets
without threading, making it more reliable on Binder environments.
"""

import ipywidgets as widgets
from IPython.display import display, clear_output, HTML
import plotly.graph_objects as go
import networkx as nx
from typing import Dict, Optional
from contract_interface import SYBContract, SYBUser
from network import Network
from utils import (
    generate_mul_eth_addresses,
    format_transaction_display,
    format_address,
    generate_random_eth_address
)
import random


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


class SYBUserInterfacePlotly:
    """Simplified UI using Plotly graphs and manual refresh (Binder-friendly)."""

    def __init__(self, contract: SYBContract, users: dict):
        """Initialize the SYB UI interface."""
        self.contract = contract
        self.users = users
        self.first_user_addr = list(users.keys())[0]
        self.first_user = users[self.first_user_addr]
        self.user_interface = self.first_user['interface']

        # State tracking
        self.last_batch_scores = None
        self.next_user_id = len(users)

        # Create widgets
        self._create_widgets()
        self._create_interface()
        self._connect_events()

    def _create_widgets(self):
        """Create UI widgets."""
        # Input widgets
        self.deposit_amount = widgets.FloatText(value=1.0, description='Amount (ETH):')
        self.withdraw_amount = widgets.FloatText(value=0.5, description='Amount (ETH):')
        self.vouch_target = widgets.Dropdown(options=self._get_other_users(), description='Target User:')
        self.unvouch_target = widgets.Dropdown(options=[], description='Target User:')

        # Action buttons
        self.deposit_btn = widgets.Button(description='💰 Deposit', button_style='primary')
        self.withdraw_btn = widgets.Button(description='💸 Withdraw', button_style='warning')
        self.vouch_btn = widgets.Button(description='👍 Vouch', button_style='success')
        self.unvouch_btn = widgets.Button(description='👎 Unvouch', button_style='danger')
        self.balance_btn = widgets.Button(description='📊 My Balance', button_style='info')

        # Submit buttons
        self.deposit_submit = widgets.Button(description='Submit', button_style='success')
        self.withdraw_submit = widgets.Button(description='Submit', button_style='success')
        self.vouch_submit = widgets.Button(description='Submit', button_style='success')
        self.unvouch_submit = widgets.Button(description='Submit', button_style='success')

        # Refresh and simulation buttons
        self.refresh_all_btn = widgets.Button(description='🔄 Refresh All', button_style='info',
                                              layout=widgets.Layout(width='150px'))
        self.simulate_txn_btn = widgets.Button(description='🎲 Simulate Transaction', button_style='primary',
                                               layout=widgets.Layout(width='180px'))
        self.create_user_btn = widgets.Button(description='👤 Create New User', button_style='success',
                                              layout=widgets.Layout(width='180px'))
        self.forge_batch_btn = widgets.Button(description='⚡ Forge Batch', button_style='warning',
                                              layout=widgets.Layout(width='150px'))

        # Display widgets
        self.queue_output = widgets.Output(layout=widgets.Layout(height='150px', overflow_y='auto'))
        self.status_output = widgets.Output(layout=widgets.Layout(height='150px', overflow_y='auto'))
        self.graph_output = widgets.Output()
        self.action_output = widgets.Output()

    def _get_other_users(self):
        """Get list of other users for dropdowns."""
        return [(f"{data['name']} ({addr[:10]}...)", addr)
                for addr, data in self.users.items() if addr != self.first_user_addr]

    def _create_interface(self):
        """Create main interface layout."""
        # Input sections (hidden by default)
        self.deposit_section = widgets.VBox([self.deposit_amount, self.deposit_submit],
                                           layout=widgets.Layout(display='none'))
        self.withdraw_section = widgets.VBox([self.withdraw_amount, self.withdraw_submit],
                                            layout=widgets.Layout(display='none'))
        self.vouch_section = widgets.VBox([self.vouch_target, self.vouch_submit],
                                         layout=widgets.Layout(display='none'))
        self.unvouch_section = widgets.VBox([self.unvouch_target, self.unvouch_submit],
                                           layout=widgets.Layout(display='none'))

        # Top control panel
        control_buttons = widgets.HBox([
            self.refresh_all_btn,
            self.simulate_txn_btn,
            self.create_user_btn,
            self.forge_batch_btn
        ], layout=widgets.Layout(justify_content='space-around', padding='10px'))

        # User action buttons
        action_buttons = widgets.HBox([
            self.deposit_btn,
            self.withdraw_btn,
            self.vouch_btn,
            self.unvouch_btn,
            self.balance_btn
        ])

        # User action panel
        user_actions = widgets.VBox([
            widgets.HTML(value="<h3>👤 User Actions</h3>"),
            action_buttons,
            self.deposit_section,
            self.withdraw_section,
            self.vouch_section,
            self.unvouch_section,
            self.action_output
        ], layout=widgets.Layout(border='2px solid #2E86AB', padding='15px'))

        # Status panel
        queue_box = widgets.VBox([
            widgets.HTML(value="<h4 style='margin: 0; padding: 5px; background: #f0f0f0;'>📋 Transaction Queue</h4>"),
            self.queue_output
        ], layout=widgets.Layout(border='2px solid #4CAF50', padding='0px', width='48%'))

        status_box = widgets.VBox([
            widgets.HTML(value="<h4 style='margin: 0; padding: 5px; background: #f0f0f0;'>📊 Network Status</h4>"),
            self.status_output
        ], layout=widgets.Layout(border='2px solid #2196F3', padding='0px', width='48%'))

        status_row = widgets.HBox([queue_box, status_box],
                                  layout=widgets.Layout(justify_content='space-between'))

        # Graph panel
        graph_panel = widgets.VBox([
            widgets.HTML(value="<h3>🌐 Network Graph</h3>"),
            self.graph_output
        ])

        # Main layout
        self.main_interface = widgets.VBox([
            control_buttons,
            status_row,
            user_actions,
            graph_panel
        ])

    def _connect_events(self):
        """Connect button events to handlers."""
        # User action buttons
        self.deposit_btn.on_click(self._show_deposit_input)
        self.withdraw_btn.on_click(self._show_withdraw_input)
        self.vouch_btn.on_click(self._show_vouch_input)
        self.unvouch_btn.on_click(self._show_unvouch_input)
        self.balance_btn.on_click(self._handle_balance)

        # Submit buttons
        self.deposit_submit.on_click(self._handle_deposit)
        self.withdraw_submit.on_click(self._handle_withdraw)
        self.vouch_submit.on_click(self._handle_vouch)
        self.unvouch_submit.on_click(self._handle_unvouch)

        # Control buttons
        self.refresh_all_btn.on_click(self._handle_refresh_all)
        self.simulate_txn_btn.on_click(self._handle_simulate_transaction)
        self.create_user_btn.on_click(self._handle_create_user)
        self.forge_batch_btn.on_click(self._handle_forge_batch)

    def _toggle_inputs(self, show_section=None):
        """Show one input section and hide others."""
        for section in [self.deposit_section, self.withdraw_section,
                       self.vouch_section, self.unvouch_section]:
            section.layout.display = 'block' if section == show_section else 'none'

    def _show_deposit_input(self, b):
        self._toggle_inputs(self.deposit_section)

    def _show_withdraw_input(self, b):
        self._toggle_inputs(self.withdraw_section)

    def _show_vouch_input(self, b):
        self._toggle_inputs(self.vouch_section)

    def _show_unvouch_input(self, b):
        self._update_unvouch_options()
        self._toggle_inputs(self.unvouch_section)

    def _update_unvouch_options(self):
        """Update unvouch options based on current vouches."""
        vouches = self.contract.vouches.get(self.first_user_addr, {})
        self.unvouch_target.options = [(f"{self.users[addr]['name']} ({addr[:10]}...)", addr)
                                      for addr, is_vouched in vouches.items() if is_vouched]

    def _handle_deposit(self, b):
        """Handle deposit action."""
        with self.action_output:
            clear_output(wait=True)
            try:
                amount = int(self.deposit_amount.value * 10**18)
                self.user_interface.deposit(amount)
                print(f"✅ Deposited {self.deposit_amount.value:.2f} ETH to queue.")
                print("💡 Click 'Refresh All' to update displays.")
            except Exception as e:
                print(f"❌ Deposit failed: {e}")

    def _handle_withdraw(self, b):
        """Handle withdraw action."""
        with self.action_output:
            clear_output(wait=True)
            try:
                amount = int(self.withdraw_amount.value * 10**18)
                self.user_interface.withdraw(amount)
                print(f"✅ Withdrew {self.withdraw_amount.value:.2f} ETH to queue.")
                print("💡 Click 'Refresh All' to update displays.")
            except Exception as e:
                print(f"❌ Withdraw failed: {e}")

    def _handle_vouch(self, b):
        """Handle vouch action."""
        with self.action_output:
            clear_output(wait=True)
            try:
                target_addr = self.vouch_target.value
                self.user_interface.vouch(target_addr)
                print(f"✅ Vouched for {self.users[target_addr]['name']}.")
                print("💡 Click 'Refresh All' to update displays.")
            except Exception as e:
                print(f"❌ Vouch failed: {e}")

    def _handle_unvouch(self, b):
        """Handle unvouch action."""
        with self.action_output:
            clear_output(wait=True)
            try:
                target_addr = self.unvouch_target.value
                self.user_interface.unvouch(target_addr)
                print(f"✅ Unvouched {self.users[target_addr]['name']}.")
                print("💡 Click 'Refresh All' to update displays.")
            except Exception as e:
                print(f"❌ Unvouch failed: {e}")

    def _handle_balance(self, b):
        """Display current user balance and score."""
        with self.action_output:
            clear_output(wait=True)
            try:
                balance = self.user_interface.get_my_balance() / 10**18
                score = self.user_interface.get_my_score()
                print(f"💰 Current Balance: {balance:.4f} ETH")
                print(f"🏆 Current Score: {score:.4f}")
                print(f"📍 Address: {self.first_user_addr}")
            except Exception as e:
                print(f"❌ Error getting balance: {e}")

    def _handle_simulate_transaction(self, b):
        """Simulate a random transaction from a random user."""
        with self.action_output:
            clear_output(wait=True)
            try:
                # Get other users (excluding connected user)
                other_users = [(addr, data) for addr, data in self.users.items()
                              if addr != self.first_user_addr]

                if not other_users:
                    print("⚠️ No other users to simulate transactions.")
                    return

                # Select random user and transaction type
                user_addr, user_data = random.choice(other_users)
                user_interface = user_data['interface']
                txn_types = ['deposit', 'withdraw', 'vouch', 'unvouch']
                txn_type = random.choice(txn_types)

                if txn_type == 'deposit':
                    amount = random.uniform(0.1, 2.0)
                    user_interface.deposit(int(amount * 10**18))
                    print(f"🎲 {user_data['name']} deposited {amount:.2f} ETH")

                elif txn_type == 'withdraw':
                    balance = user_interface.get_my_balance()
                    if balance > 0:
                        max_withdraw = balance * 0.5
                        amount = random.uniform(0.1 * 10**18, min(max_withdraw, 1.0 * 10**18))
                        user_interface.withdraw(int(amount))
                        print(f"🎲 {user_data['name']} withdrew {amount/10**18:.2f} ETH")
                    else:
                        print(f"⚠️ {user_data['name']} has no balance to withdraw")

                elif txn_type == 'vouch':
                    possible_targets = [addr for addr in self.users.keys()
                                      if addr != user_addr and addr != self.first_user_addr]
                    if possible_targets:
                        target = random.choice(possible_targets)
                        vouches = self.contract.vouches.get(user_addr, {})
                        if not vouches.get(target, False):
                            user_interface.vouch(target)
                            print(f"🎲 {user_data['name']} vouched for {self.users[target]['name']}")
                        else:
                            print(f"⚠️ {user_data['name']} already vouched for selected user")
                    else:
                        print("⚠️ No valid vouch targets")

                elif txn_type == 'unvouch':
                    vouches = self.contract.vouches.get(user_addr, {})
                    active_vouches = [addr for addr, is_vouched in vouches.items() if is_vouched]
                    if active_vouches:
                        target = random.choice(active_vouches)
                        user_interface.unvouch(target)
                        print(f"🎲 {user_data['name']} unvouched {self.users[target]['name']}")
                    else:
                        print(f"⚠️ {user_data['name']} has no active vouches")

                print("💡 Click 'Refresh All' to see updates.")

            except Exception as e:
                print(f"❌ Simulation error: {e}")

    def _handle_create_user(self, b):
        """Create a new user with random initial deposit."""
        with self.action_output:
            clear_output(wait=True)
            try:
                from contract_interface import SYBUser

                # Generate new user
                new_addr = generate_random_eth_address()
                user_name = f"User {self.next_user_id}"
                initial_deposit = random.uniform(0.5, 3.0)

                # Create account
                self.contract.deposit(new_addr, int(initial_deposit * 10**18))
                user_interface = SYBUser(self.contract, new_addr)

                # Add to users dict
                self.users[new_addr] = {
                    'interface': user_interface,
                    'name': user_name,
                    'address': new_addr
                }

                self.next_user_id += 1

                # Update dropdowns
                self.vouch_target.options = self._get_other_users()

                print(f"✅ Created {user_name} with {initial_deposit:.2f} ETH")
                print(f"📍 Address: {new_addr[:12]}...")
                print("💡 Click 'Refresh All' to see the updated network.")

            except Exception as e:
                print(f"❌ User creation failed: {e}")

    def _handle_forge_batch(self, b):
        """Manually forge a batch if enough transactions are queued."""
        with self.action_output:
            clear_output(wait=True)
            try:
                txns_count = len(self.contract.unprocessed_txns)

                if txns_count < self.contract.batch_size:
                    print(f"⚠️ Not enough transactions to forge batch.")
                    print(f"   Need {self.contract.batch_size}, have {txns_count}")
                    return

                # Save current scores before forging
                self.last_batch_scores = self.contract.network.compute_score('pagerank')

                # Forge batch
                print("⚡ Forging batch...")
                result = self.contract.forge_batch()

                if result:
                    print(f"✅ Batch #{self.contract.last_forged_batch} forged successfully!")
                    print(f"   Processed {len(result.transactions_processed)} transactions")
                    print("💡 Click 'Refresh All' to see updated scores and graph.")
                else:
                    print("❌ Batch forging failed.")

            except Exception as e:
                print(f"❌ Batch forging error: {e}")

    def _handle_refresh_all(self, b):
        """Refresh all displays."""
        self._update_queue_display()
        self._update_status_display()
        self._update_network_graph()

        with self.action_output:
            clear_output(wait=True)
            print("✅ All displays refreshed!")

    def _update_queue_display(self):
        """Update transaction queue display."""
        with self.queue_output:
            clear_output(wait=True)
            txns = self.contract.unprocessed_txns

            if not txns:
                print("Queue is empty")
            else:
                print(f"Queued transactions ({len(txns)}/{self.contract.batch_size}):\n")
                for i, txn in enumerate(txns, 1):
                    txn_str = format_transaction_display(txn, self.users, index=i)
                    print(txn_str)

    def _update_status_display(self):
        """Update network status display."""
        with self.status_output:
            clear_output(wait=True)
            try:
                num_users = len(self.users)
                pending_txns = len(self.contract.unprocessed_txns)
                batch_size = self.contract.batch_size
                last_batch = self.contract.last_forged_batch

                # Calculate total deposits
                total_deposits = sum(
                    data['interface'].get_my_balance() / 10**18
                    for data in self.users.values()
                )

                print(f"👥 Total Users: {num_users}")
                print(f"💰 Total Deposits: {total_deposits:.4f} ETH")
                print(f"⏳ Pending Txns: {pending_txns} / {batch_size}")
                print(f"📊 Algorithm: {self.contract.scoring_algorithm}")
                print(f"🔄 Last Batch: #{last_batch}")

            except Exception as e:
                print(f"Error: {e}")

    def _update_network_graph(self):
        """Update network graph using Plotly."""
        with self.graph_output:
            clear_output(wait=True)
            try:
                G = self.contract.network.graph

                if G.number_of_nodes() == 0:
                    print("Network is empty")
                    return

                # Get current scores
                current_scores = self.contract.network.compute_score('pagerank')

                # Create layout
                pos = nx.spring_layout(G, seed=42)

                # Create edge traces
                edge_x = []
                edge_y = []
                for edge in G.edges():
                    x0, y0 = pos[edge[0]]
                    x1, y1 = pos[edge[1]]
                    edge_x.extend([x0, x1, None])
                    edge_y.extend([y0, y1, None])

                edge_trace = go.Scatter(
                    x=edge_x, y=edge_y,
                    line=dict(width=1, color='#888'),
                    hoverinfo='none',
                    mode='lines'
                )

                # Create node traces
                node_x = []
                node_y = []
                node_text = []
                node_size = []
                node_color = []

                for node in G.nodes():
                    x, y = pos[node]
                    node_x.append(x)
                    node_y.append(y)

                    # Get node info
                    addr = self.contract.idx_to_address.get(node, "Unknown")
                    user_name = self.users.get(addr, {}).get('name', f'Node {node}')
                    balance = self.contract.network.balance_list[node] if node < len(self.contract.network.balance_list) else 0
                    score = current_scores[node] if node < len(current_scores) else 0

                    node_text.append(f"{user_name}<br>Score: {score:.4f}<br>Balance: {balance:.4f} ETH")
                    node_size.append(max(10, balance * 50))  # Size based on balance
                    node_color.append(score)  # Color based on score

                node_trace = go.Scatter(
                    x=node_x, y=node_y,
                    mode='markers',
                    hoverinfo='text',
                    text=node_text,
                    marker=dict(
                        showscale=True,
                        colorscale='Viridis',
                        color=node_color,
                        size=node_size,
                        colorbar=dict(
                            thickness=15,
                            title=dict(
                                text='Score',
                                side='right'
                            ),
                            xanchor='left'
                        ),
                        line=dict(width=2, color='white')
                    )
                )

                # Create figure
                fig = go.Figure(data=[edge_trace, node_trace],
                             layout=go.Layout(
                                title=dict(
                                    text=f'SYB Network - {G.number_of_nodes()} nodes, {G.number_of_edges()} edges',
                                    font=dict(size=16)
                                ),
                                showlegend=False,
                                hovermode='closest',
                                margin=dict(b=20,l=5,r=5,t=40),
                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                height=600
                             ))

                fig.show()

            except Exception as e:
                print(f"Graph error: {e}")

    def display(self):
        """Display the interface."""
        print(f"🔐 Connected as: {self.first_user['name']} ({self.first_user_addr[:12]}...)")
        print("\n💡 Tips:")
        print("  • Use action buttons to queue transactions")
        print("  • Click 'Simulate Transaction' to generate random activity")
        print("  • Click 'Forge Batch' when queue reaches batch size")
        print("  • Click 'Refresh All' to update all displays\n")

        # Initial display updates
        self._update_queue_display()
        self._update_status_display()
        self._update_network_graph()

        # Show interface
        display(self.main_interface)
