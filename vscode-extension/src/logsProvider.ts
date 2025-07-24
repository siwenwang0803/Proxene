import * as vscode from 'vscode';
import { ProxeneManager, ProxeneLogEntry } from './proxeneManager';

export class LogsProvider implements vscode.TreeDataProvider<LogTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<LogTreeItem | undefined | null | void> = new vscode.EventEmitter<LogTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<LogTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private proxeneManager: ProxeneManager) {
        // Listen for new logs
        this.proxeneManager.on('logAdded', () => {
            this.refresh();
        });
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: LogTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: LogTreeItem): Thenable<LogTreeItem[]> {
        if (!element) {
            // Root level - show recent logs
            const logs = this.proxeneManager.getLogs();
            return Promise.resolve(logs.slice(-20).reverse().map(log => new LogTreeItem(log)));
        }
        
        return Promise.resolve([]);
    }
}

class LogTreeItem extends vscode.TreeItem {
    constructor(public readonly logEntry: ProxeneLogEntry) {
        super(`${logEntry.method} ${logEntry.path}`, vscode.TreeItemCollapsibleState.None);

        this.tooltip = this.buildTooltip();
        this.description = this.buildDescription();
        this.contextValue = 'logEntry';
        
        // Set icon based on status
        this.iconPath = new vscode.ThemeIcon(
            logEntry.status >= 400 ? 'error' : 
            logEntry.status >= 300 ? 'warning' : 
            'check'
        );

        // Command to open log details
        this.command = {
            command: 'proxene.openLogDetails',
            title: 'Open Log Details',
            arguments: [logEntry]
        };
    }

    private buildTooltip(): string {
        const parts = [
            `${this.logEntry.method} ${this.logEntry.path}`,
            `Status: ${this.logEntry.status}`,
            `Time: ${this.logEntry.timestamp.toLocaleTimeString()}`
        ];

        if (this.logEntry.model) {
            parts.push(`Model: ${this.logEntry.model}`);
        }

        if (this.logEntry.cost) {
            parts.push(`Cost: $${this.logEntry.cost.toFixed(6)}`);
        }

        if (this.logEntry.piiFindings) {
            parts.push(`PII: ${this.logEntry.piiFindings} findings`);
        }

        return parts.join('\n');
    }

    private buildDescription(): string {
        const parts = [];
        
        // Status with color coding
        if (this.logEntry.status >= 400) {
            parts.push(`❌ ${this.logEntry.status}`);
        } else if (this.logEntry.status >= 300) {
            parts.push(`⚠️ ${this.logEntry.status}`);
        } else {
            parts.push(`✅ ${this.logEntry.status}`);
        }

        // Cost if available
        if (this.logEntry.cost) {
            parts.push(`💰 $${this.logEntry.cost.toFixed(4)}`);
        }

        // PII warnings
        if (this.logEntry.piiFindings) {
            parts.push(`🔒 ${this.logEntry.piiFindings}`);
        }

        // Time
        parts.push(`⏰ ${this.logEntry.timestamp.toLocaleTimeString()}`);

        return parts.join(' ');
    }
}