import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { EventEmitter } from 'events';

export interface ProxeneLogEntry {
    timestamp: Date;
    method: string;
    path: string;
    model?: string;
    cost?: number;
    piiFindings?: number;
    status: number;
    duration?: number;
    id: string;
}

export class ProxeneManager extends EventEmitter {
    private context: vscode.ExtensionContext;
    private proxyProcess: cp.ChildProcess | null = null;
    private isRunning: boolean = false;
    private logs: ProxeneLogEntry[] = [];
    private outputChannel: vscode.OutputChannel;

    constructor(context: vscode.ExtensionContext) {
        super();
        this.context = context;
        this.outputChannel = vscode.window.createOutputChannel('Proxene');
    }

    public startProxy(): void {
        if (this.isRunning) {
            vscode.window.showInformationMessage('Proxene proxy is already running');
            return;
        }

        const config = vscode.workspace.getConfiguration('proxene');
        const port = config.get<number>('proxyPort', 8081);
        const logLevel = config.get<string>('logLevel', 'info');

        // Try to find proxene executable
        const command = this.findProxeneCommand();
        if (!command) {
            vscode.window.showErrorMessage('Proxene not found. Please install Proxene first.');
            return;
        }

        this.outputChannel.clear();
        this.outputChannel.show();
        this.outputChannel.appendLine('Starting Proxene proxy...');

        // Start the proxy process
        this.proxyProcess = cp.spawn('python', ['-m', 'uvicorn', 'proxene.main:app', '--host', '0.0.0.0', '--port', port.toString(), '--log-level', logLevel], {
            cwd: this.getWorkspaceRoot(),
            env: { ...process.env, PYTHONPATH: this.getWorkspaceRoot() }
        });

        this.proxyProcess.stdout?.on('data', (data) => {
            const output = data.toString();
            this.outputChannel.appendLine(output);
            this.parseLogOutput(output);
        });

        this.proxyProcess.stderr?.on('data', (data) => {
            this.outputChannel.appendLine(`Error: ${data.toString()}`);
        });

        this.proxyProcess.on('close', (code) => {
            this.outputChannel.appendLine(`Proxene proxy exited with code ${code}`);
            this.isRunning = false;
            this.proxyProcess = null;
            this.emit('stateChange', false);
        });

        this.proxyProcess.on('error', (error) => {
            vscode.window.showErrorMessage(`Failed to start Proxene: ${error.message}`);
            this.outputChannel.appendLine(`Failed to start: ${error.message}`);
            this.isRunning = false;
            this.emit('stateChange', false);
        });

        // Give it a moment to start
        setTimeout(() => {
            if (this.proxyProcess && !this.proxyProcess.killed) {
                this.isRunning = true;
                this.emit('stateChange', true);
                vscode.window.showInformationMessage(`Proxene proxy started on port ${port}`);
            }
        }, 2000);
    }

    public stopProxy(): void {
        if (!this.isRunning || !this.proxyProcess) {
            vscode.window.showInformationMessage('Proxene proxy is not running');
            return;
        }

        this.proxyProcess.kill();
        this.isRunning = false;
        this.emit('stateChange', false);
        vscode.window.showInformationMessage('Proxene proxy stopped');
    }

    public getLogs(): ProxeneLogEntry[] {
        return this.logs.slice(-100); // Return last 100 logs
    }

    public onStateChange(callback: (isRunning: boolean) => void): void {
        this.on('stateChange', callback);
    }

    public openLogDetails(logEntry: ProxeneLogEntry): void {
        // Create a temporary document with log details
        const content = this.formatLogDetails(logEntry);
        
        vscode.workspace.openTextDocument({
            content: content,
            language: 'json'
        }).then(doc => {
            vscode.window.showTextDocument(doc);
        });
    }

    private findProxeneCommand(): string | null {
        // Try different ways to find proxene
        const workspaceRoot = this.getWorkspaceRoot();
        
        // Check if we're in a Poetry project
        const pyprojectPath = path.join(workspaceRoot, 'pyproject.toml');
        if (require('fs').existsSync(pyprojectPath)) {
            return 'poetry run python';
        }

        // Check if proxene is installed globally
        try {
            cp.execSync('proxene --help', { stdio: 'ignore' });
            return 'proxene';
        } catch {
            // Not installed globally
        }

        // Check if we can run python -m proxene
        try {
            cp.execSync('python -m proxene --help', { stdio: 'ignore' });
            return 'python -m proxene';
        } catch {
            // Not available
        }

        return null;
    }

    private getWorkspaceRoot(): string {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            return workspaceFolders[0].uri.fsPath;
        }
        return process.cwd();
    }

    private parseLogOutput(output: string): void {
        // Parse uvicorn log output to extract request information
        const lines = output.split('\n');
        
        for (const line of lines) {
            // Look for HTTP request logs
            const httpMatch = line.match(/INFO:.*"(GET|POST|PUT|DELETE|PATCH) ([^"]+)" (\d+)/);
            if (httpMatch) {
                const [, method, path, status] = httpMatch;
                
                const logEntry: ProxeneLogEntry = {
                    timestamp: new Date(),
                    method,
                    path,
                    status: parseInt(status),
                    id: this.generateId()
                };

                // Try to extract additional info from the path or subsequent logs
                if (path.includes('/v1/chat/completions')) {
                    logEntry.model = 'gpt-3.5-turbo'; // Default, should be parsed from request
                }

                this.logs.push(logEntry);
                this.emit('logAdded', logEntry);
            }

            // Look for Proxene-specific logs (cost, PII, etc.)
            if (line.includes('_proxene_cost')) {
                const costMatch = line.match(/cost.*?(\d+\.\d+)/);
                if (costMatch && this.logs.length > 0) {
                    this.logs[this.logs.length - 1].cost = parseFloat(costMatch[1]);
                }
            }

            if (line.includes('_proxene_pii')) {
                if (this.logs.length > 0) {
                    this.logs[this.logs.length - 1].piiFindings = 1; // Simplified
                }
            }
        }
    }

    private formatLogDetails(logEntry: ProxeneLogEntry): string {
        return JSON.stringify({
            timestamp: logEntry.timestamp.toISOString(),
            request: {
                method: logEntry.method,
                path: logEntry.path,
                status: logEntry.status
            },
            ai: {
                model: logEntry.model,
                cost: logEntry.cost ? `$${logEntry.cost.toFixed(6)}` : 'N/A',
                piiFindings: logEntry.piiFindings || 0
            },
            metadata: {
                id: logEntry.id,
                duration: logEntry.duration || 'N/A'
            }
        }, null, 2);
    }

    private generateId(): string {
        return Math.random().toString(36).substr(2, 9);
    }

    public dispose(): void {
        if (this.proxyProcess) {
            this.proxyProcess.kill();
        }
        this.outputChannel.dispose();
    }
}