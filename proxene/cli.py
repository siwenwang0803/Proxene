"""CLI for Proxene - local request replay and debugging"""

import click
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
import yaml
from datetime import datetime
import logging

from proxene.guards.cost_guard import CostGuard
from proxene.policies.loader import PolicyLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Proxene CLI - Debug and replay LLM requests locally"""
    pass


@cli.command()
@click.argument('request_file', type=click.Path(exists=True))
@click.option('--policy', '-p', help='Policy file to use', default='policies/default.yaml')
@click.option('--dry-run', is_flag=True, help='Simulate without making actual API calls')
def replay(request_file: str, policy: str, dry_run: bool):
    """Replay a saved request through Proxene governance"""
    
    # Load request
    with open(request_file, 'r') as f:
        request_data = json.load(f)
        
    # Load policy
    policy_loader = PolicyLoader()
    if Path(policy).exists():
        with open(policy, 'r') as f:
            policy_data = yaml.safe_load(f)
    else:
        policy_data = policy_loader.get_active_policy()
        
    click.echo(f"Replaying request from: {request_file}")
    click.echo(f"Using policy: {policy_data.get('name', 'Unknown')}")
    
    # Run async replay
    asyncio.run(_replay_request(request_data, policy_data, dry_run))


async def _replay_request(request_data: Dict[str, Any], policy: Dict[str, Any], dry_run: bool):
    """Async replay implementation"""
    
    # Initialize cost guard
    cost_guard = CostGuard()
    
    # 1. Display request info
    click.echo("\n" + "="*50)
    click.echo("REQUEST ANALYSIS")
    click.echo("="*50)
    
    model = request_data.get("model", "gpt-3.5-turbo")
    messages = request_data.get("messages", [])
    
    click.echo(f"Model: {model}")
    click.echo(f"Messages: {len(messages)}")
    
    # 2. Token estimation
    input_tokens = cost_guard.estimate_request_tokens(request_data)
    max_tokens = request_data.get("max_tokens", 500)
    
    click.echo(f"\nEstimated tokens:")
    click.echo(f"  Input: {input_tokens}")
    click.echo(f"  Max output: {max_tokens}")
    
    # 3. Cost estimation
    estimated_cost = cost_guard.calculate_cost(model, input_tokens, max_tokens)
    click.echo(f"\nEstimated cost: ${estimated_cost:.4f}")
    
    # 4. Policy checks
    click.echo("\n" + "="*50)
    click.echo("POLICY CHECKS")
    click.echo("="*50)
    
    # Check cost limits
    if policy.get("cost_limits"):
        limits = policy["cost_limits"]
        click.echo("\nCost limits:")
        
        if "max_per_request" in limits:
            limit = limits["max_per_request"]
            passed = estimated_cost <= limit
            status = click.style("PASS", fg="green") if passed else click.style("FAIL", fg="red")
            click.echo(f"  Per request: ${limit:.2f} [{status}]")
            
    # Check caching
    if policy.get("caching", {}).get("enabled"):
        click.echo("\nCaching: ENABLED")
        click.echo(f"  TTL: {policy['caching'].get('ttl_seconds', 3600)}s")
    else:
        click.echo("\nCaching: DISABLED")
        
    # 5. Execute request (if not dry run)
    if not dry_run:
        click.echo("\n" + "="*50)
        click.echo("EXECUTING REQUEST")
        click.echo("="*50)
        
        try:
            # Get API key
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                click.echo(click.style("ERROR: OPENAI_API_KEY not set", fg="red"))
                return
                
            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=request_data,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Display results
                    usage = result.get("usage", {})
                    actual_input = usage.get("prompt_tokens", 0)
                    actual_output = usage.get("completion_tokens", 0)
                    actual_cost = cost_guard.calculate_cost(model, actual_input, actual_output)
                    
                    click.echo(f"\nActual tokens:")
                    click.echo(f"  Input: {actual_input}")
                    click.echo(f"  Output: {actual_output}")
                    click.echo(f"  Total: {usage.get('total_tokens', 0)}")
                    
                    click.echo(f"\nActual cost: ${actual_cost:.4f}")
                    
                    # Show response
                    click.echo("\nResponse:")
                    for choice in result.get("choices", []):
                        content = choice.get("message", {}).get("content", "")
                        click.echo(f"  {content[:100]}{'...' if len(content) > 100 else ''}")
                        
                else:
                    click.echo(click.style(f"ERROR: {response.status_code} - {response.text}", fg="red"))
                    
        except Exception as e:
            click.echo(click.style(f"ERROR: {str(e)}", fg="red"))
    else:
        click.echo("\n[DRY RUN - No API call made]")


@cli.command()
@click.argument('log_dir', type=click.Path(), default='logs')
def save_request(log_dir: str):
    """Save incoming requests for replay (interactive)"""
    
    # Create example request
    example = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    # Save to file
    Path(log_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{log_dir}/request_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(example, f, indent=2)
        
    click.echo(f"Saved example request to: {filename}")
    click.echo("\nYou can now replay it with:")
    click.echo(f"  proxene replay {filename}")


@cli.command()
def validate_policies():
    """Validate all policy files"""
    
    policy_loader = PolicyLoader()
    policies = policy_loader.load_policies()
    
    click.echo(f"Found {len(policies)} policies\n")
    
    for name, policy in policies.items():
        errors = policy_loader.validate_policy(policy)
        
        if errors:
            click.echo(f"{click.style(name, fg='red')}: {len(errors)} errors")
            for error in errors:
                click.echo(f"  - {error}")
        else:
            click.echo(f"{click.style(name, fg='green')}: Valid")
            
    click.echo("\n" + "="*50)
    
    # Show active policy
    active = policy_loader.get_active_policy()
    if active:
        click.echo(f"Active policy: {active.get('name', 'Unknown')}")


@cli.command()
@click.option('--coverage', is_flag=True, help='Run with coverage report')
def test(coverage: bool):
    """Run test suite"""
    
    import subprocess
    import sys
    
    cmd = ["python", "-m", "pytest", "tests/"]
    
    if coverage:
        cmd.extend(["--cov=proxene", "--cov-report=term-missing"])
    
    click.echo("Running Proxene test suite...")
    result = subprocess.run(cmd, cwd=".")
    
    if result.returncode == 0:
        click.echo(click.style("\n✅ All tests passed!", fg="green"))
    else:
        click.echo(click.style("\n❌ Some tests failed", fg="red"))
        sys.exit(1)


@cli.command()
@click.option('--port', '-p', default=8501, help='Port for dashboard (default: 8501)')
@click.option('--host', '-h', default='0.0.0.0', help='Host for dashboard (default: 0.0.0.0)')
def dashboard(port: int, host: str):
    """Launch the Proxene dashboard"""
    
    import subprocess
    import sys
    import os
    
    # Find dashboard app
    dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dashboard')
    dashboard_app = os.path.join(dashboard_dir, 'app.py')
    
    if not os.path.exists(dashboard_app):
        click.echo(click.style("❌ Dashboard not found!", fg="red"))
        click.echo("Make sure you're in the Proxene project directory")
        sys.exit(1)
    
    click.echo("🚀 Starting Proxene Dashboard...")
    click.echo(f"📊 Dashboard: http://localhost:{port}")
    click.echo("🛑 Press Ctrl+C to stop")
    
    try:
        subprocess.run([
            sys.executable, '-m', 'streamlit', 'run',
            dashboard_app,
            '--server.port', str(port),
            '--server.address', host,
            '--theme.base', 'dark'
        ], cwd=dashboard_dir)
    except KeyboardInterrupt:
        click.echo(click.style("\n👋 Dashboard stopped", fg="green"))
    except Exception as e:
        click.echo(click.style(f"❌ Failed to start dashboard: {e}", fg="red"))
        sys.exit(1)


if __name__ == "__main__":
    cli()