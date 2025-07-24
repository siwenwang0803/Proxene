import * as vscode from 'vscode';
import { ProxeneManager } from './proxeneManager';
import { LogsProvider } from './logsProvider';
import { ControlProvider } from './controlProvider';

let proxeneManager: ProxeneManager;
let logsProvider: LogsProvider;
let controlProvider: ControlProvider;

export function activate(context: vscode.ExtensionContext) {
    console.log('Proxene extension is now active!');

    // Initialize managers
    proxeneManager = new ProxeneManager(context);
    logsProvider = new LogsProvider(proxeneManager);
    controlProvider = new ControlProvider(proxeneManager);

    // Register tree data providers
    vscode.window.registerTreeDataProvider('proxeneControl', controlProvider);
    vscode.window.registerTreeDataProvider('proxeneLogs', logsProvider);

    // Register commands
    const commands = [
        vscode.commands.registerCommand('proxene.startProxy', () => {
            proxeneManager.startProxy();
        }),
        
        vscode.commands.registerCommand('proxene.stopProxy', () => {
            proxeneManager.stopProxy();
        }),
        
        vscode.commands.registerCommand('proxene.showLogs', () => {
            vscode.commands.executeCommand('workbench.view.explorer');
            vscode.commands.executeCommand('proxeneLogs.focus');
        }),
        
        vscode.commands.registerCommand('proxene.openDashboard', () => {
            const config = vscode.workspace.getConfiguration('proxene');
            const dashboardUrl = config.get<string>('dashboardUrl', 'http://localhost:8501');
            vscode.env.openExternal(vscode.Uri.parse(dashboardUrl));
        }),
        
        vscode.commands.registerCommand('proxene.refreshLogs', () => {
            logsProvider.refresh();
        }),

        vscode.commands.registerCommand('proxene.openLogDetails', (logItem) => {
            proxeneManager.openLogDetails(logItem);
        })
    ];

    // Add all commands to subscriptions
    commands.forEach(cmd => context.subscriptions.push(cmd));

    // Set context for when Proxene is available
    checkProxeneAvailability();

    // Auto-start if configured
    const config = vscode.workspace.getConfiguration('proxene');
    if (config.get<boolean>('autoStart', false)) {
        proxeneManager.startProxy();
    }

    // Status bar item
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'proxene.showLogs';
    statusBarItem.text = '$(shield) Proxene';
    statusBarItem.tooltip = 'Proxene AI Governance Proxy';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Update status bar based on proxy state
    proxeneManager.onStateChange((isRunning: boolean) => {
        if (isRunning) {
            statusBarItem.text = '$(shield) Proxene $(check)';
            statusBarItem.tooltip = 'Proxene proxy is running';
            vscode.commands.executeCommand('setContext', 'proxeneActive', true);
        } else {
            statusBarItem.text = '$(shield) Proxene $(x)';
            statusBarItem.tooltip = 'Proxene proxy is stopped';
            vscode.commands.executeCommand('setContext', 'proxeneActive', false);
        }
        
        // Refresh providers
        controlProvider.refresh();
        logsProvider.refresh();
    });
}

function checkProxeneAvailability() {
    // Check if proxene is installed or available in workspace
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders) {
        // Look for pyproject.toml with proxene or package.json with proxene
        for (const folder of workspaceFolders) {
            const pyprojectPath = vscode.Uri.joinPath(folder.uri, 'pyproject.toml');
            const packagePath = vscode.Uri.joinPath(folder.uri, 'package.json');
            
            // For now, just set it to true if we have a workspace
            vscode.commands.executeCommand('setContext', 'workspaceHasProxene', true);
            return;
        }
    }
    
    vscode.commands.executeCommand('setContext', 'workspaceHasProxene', false);
}

export function deactivate() {
    if (proxeneManager) {
        proxeneManager.dispose();
    }
}