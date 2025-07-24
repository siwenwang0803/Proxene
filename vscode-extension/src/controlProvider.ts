import * as vscode from 'vscode';
import { ProxeneManager } from './proxeneManager';

export class ControlProvider implements vscode.TreeDataProvider<ControlTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<ControlTreeItem | undefined | null | void> = new vscode.EventEmitter<ControlTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<ControlTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private proxeneManager: ProxeneManager) {
        // Listen for state changes
        this.proxeneManager.onStateChange(() => {
            this.refresh();
        });
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: ControlTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: ControlTreeItem): Thenable<ControlTreeItem[]> {
        if (!element) {
            // Root level - show control options
            const items = [
                new ControlTreeItem(
                    'Proxy Status',
                    'status',
                    this.proxeneManager['isRunning'] ? 'Running ✅' : 'Stopped ❌',
                    undefined,
                    vscode.TreeItemCollapsibleState.None
                ),
                new ControlTreeItem(
                    'Controls',
                    'controls',
                    '',
                    undefined,
                    vscode.TreeItemCollapsibleState.Expanded
                ),
                new ControlTreeItem(
                    'Configuration',
                    'config',
                    '',
                    undefined,
                    vscode.TreeItemCollapsibleState.Collapsed
                )
            ];

            return Promise.resolve(items);
        }

        if (element.contextValue === 'controls') {
            const isRunning = this.proxeneManager['isRunning'];
            return Promise.resolve([
                new ControlTreeItem(
                    'Start Proxy',
                    'startCommand',
                    isRunning ? 'Already running' : 'Click to start',
                    isRunning ? undefined : 'proxene.startProxy',
                    vscode.TreeItemCollapsibleState.None
                ),
                new ControlTreeItem(
                    'Stop Proxy',
                    'stopCommand',
                    !isRunning ? 'Not running' : 'Click to stop',
                    !isRunning ? undefined : 'proxene.stopProxy',
                    vscode.TreeItemCollapsibleState.None
                ),
                new ControlTreeItem(
                    'View Logs',
                    'logsCommand',
                    'Open request logs',
                    'proxene.showLogs',
                    vscode.TreeItemCollapsibleState.None
                ),
                new ControlTreeItem(
                    'Open Dashboard',
                    'dashboardCommand',
                    'Open web dashboard',
                    'proxene.openDashboard',
                    vscode.TreeItemCollapsibleState.None
                )
            ]);
        }

        if (element.contextValue === 'config') {
            const config = vscode.workspace.getConfiguration('proxene');
            return Promise.resolve([
                new ControlTreeItem(
                    `Port: ${config.get('proxyPort', 8081)}`,
                    'configItem',
                    'Proxy server port',
                    undefined,
                    vscode.TreeItemCollapsibleState.None
                ),
                new ControlTreeItem(
                    `Auto Start: ${config.get('autoStart', false) ? 'Yes' : 'No'}`,
                    'configItem',
                    'Start proxy automatically',
                    undefined,
                    vscode.TreeItemCollapsibleState.None
                ),
                new ControlTreeItem(
                    `Log Level: ${config.get('logLevel', 'info')}`,
                    'configItem',
                    'Logging verbosity',
                    undefined,
                    vscode.TreeItemCollapsibleState.None
                )
            ]);
        }

        return Promise.resolve([]);
    }
}

class ControlTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly contextValue: string,
        public readonly description: string,
        public readonly commandId?: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None
    ) {
        super(label, collapsibleState);

        this.description = description;
        this.tooltip = `${label}: ${description}`;

        if (commandId) {
            this.command = {
                command: commandId,
                title: label
            };
        }

        // Set appropriate icons
        switch (contextValue) {
            case 'status':
                this.iconPath = new vscode.ThemeIcon('pulse');
                break;
            case 'controls':
                this.iconPath = new vscode.ThemeIcon('settings-gear');
                break;
            case 'config':
                this.iconPath = new vscode.ThemeIcon('settings');
                break;
            case 'startCommand':
                this.iconPath = new vscode.ThemeIcon('play');
                break;
            case 'stopCommand':
                this.iconPath = new vscode.ThemeIcon('stop');
                break;
            case 'logsCommand':
                this.iconPath = new vscode.ThemeIcon('output');
                break;
            case 'dashboardCommand':
                this.iconPath = new vscode.ThemeIcon('dashboard');
                break;
            case 'configItem':
                this.iconPath = new vscode.ThemeIcon('gear');
                break;
        }
    }
}