#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::{Command, Child, Stdio};
use std::sync::{Arc, Mutex};
use tauri::{Manager, State};

// RAPP OS process state
struct RappOsState {
    process: Arc<Mutex<Option<Child>>>,
    port: u16,
}

impl Default for RappOsState {
    fn default() -> Self {
        Self {
            process: Arc::new(Mutex::new(None)),
            port: 7071,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RappConfig {
    pub rapp_home: String,
    pub azure_configured: bool,
    pub projects: Vec<ProjectInfo>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ProjectInfo {
    pub name: String,
    pub path: String,
    pub created: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct InstallResult {
    pub success: bool,
    pub message: String,
    pub path: Option<String>,
}

// Configuration
#[tauri::command]
fn get_rapp_home() -> String {
    dirs::home_dir().unwrap_or_default().join(".rapp").to_string_lossy().to_string()
}

#[tauri::command]
fn get_config() -> Result<RappConfig, String> {
    let home = dirs::home_dir().ok_or("No home directory")?;
    let config_path = home.join(".rapp/config.json");

    if config_path.exists() {
        let content = std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())
    } else {
        Ok(RappConfig {
            rapp_home: home.join(".rapp").to_string_lossy().to_string(),
            azure_configured: false,
            projects: vec![],
        })
    }
}

#[tauri::command]
fn save_config(config: RappConfig) -> Result<(), String> {
    let home = dirs::home_dir().ok_or("No home directory")?;
    let rapp_home = home.join(".rapp");
    std::fs::create_dir_all(&rapp_home).map_err(|e| e.to_string())?;

    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(rapp_home.join("config.json"), content).map_err(|e| e.to_string())
}

// RAPP Store & Hub
#[tauri::command]
async fn fetch_manifest(url: String) -> Result<String, String> {
    reqwest::get(&url).await.map_err(|e| e.to_string())?
        .text().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn install_agent(agent_id: String, path: String, filename: String) -> Result<InstallResult, String> {
    let home = dirs::home_dir().ok_or("No home directory")?;
    let agents_dir = home.join(".rapp/agents");
    std::fs::create_dir_all(&agents_dir).map_err(|e| e.to_string())?;

    let url = format!("https://raw.githubusercontent.com/kody-w/RAPP_Store/main/{}/{}", path, filename);
    let content = reqwest::get(&url).await.map_err(|e| e.to_string())?
        .text().await.map_err(|e| e.to_string())?;

    let agent_file = agents_dir.join(&filename);
    std::fs::write(&agent_file, &content).map_err(|e| e.to_string())?;

    Ok(InstallResult {
        success: true,
        message: format!("Installed {}", agent_id),
        path: Some(agent_file.to_string_lossy().to_string()),
    })
}

#[tauri::command]
async fn install_skill(skill_id: String, path: String) -> Result<InstallResult, String> {
    let home = dirs::home_dir().ok_or("No home directory")?;
    let skill_dir = home.join(".rapp/skills").join(&skill_id);
    std::fs::create_dir_all(&skill_dir).map_err(|e| e.to_string())?;

    let url = format!("https://raw.githubusercontent.com/kody-w/RAPP_Store/main/{}/SKILL.md", path);
    let content = reqwest::get(&url).await.map_err(|e| e.to_string())?
        .text().await.map_err(|e| e.to_string())?;

    std::fs::write(skill_dir.join("SKILL.md"), &content).map_err(|e| e.to_string())?;

    Ok(InstallResult {
        success: true,
        message: format!("Installed {}", skill_id),
        path: Some(skill_dir.to_string_lossy().to_string()),
    })
}

#[tauri::command]
async fn clone_implementation(repo: String, name: String) -> Result<InstallResult, String> {
    let home = dirs::home_dir().ok_or("No home directory")?;
    let target = home.join(".rapp/projects").join(&name);

    if target.exists() {
        return Ok(InstallResult { success: false, message: "Already exists".into(), path: None });
    }

    let output = Command::new("git")
        .args(["clone", "--depth", "1", &repo, target.to_str().unwrap()])
        .output().map_err(|e| e.to_string())?;

    Ok(InstallResult {
        success: output.status.success(),
        message: if output.status.success() { "Cloned".into() } else { String::from_utf8_lossy(&output.stderr).to_string() },
        path: Some(target.to_string_lossy().to_string()),
    })
}

// Projects
#[tauri::command]
fn create_project(name: String) -> Result<InstallResult, String> {
    let home = dirs::home_dir().ok_or("No home directory")?;
    let project = home.join(".rapp/projects").join(&name);

    if project.exists() {
        return Ok(InstallResult { success: false, message: "Already exists".into(), path: None });
    }

    std::fs::create_dir_all(project.join("agents")).map_err(|e| e.to_string())?;

    let rapp_json = serde_json::json!({
        "name": name,
        "version": "1.0.0",
        "dependencies": { "rapp_store": { "agents": [], "skills": [] } }
    });
    std::fs::write(project.join("rapp.json"), serde_json::to_string_pretty(&rapp_json).unwrap()).ok();
    std::fs::write(project.join("main.py"), "#!/usr/bin/env python3\nprint('Hello from RAPP!')").ok();

    Ok(InstallResult {
        success: true,
        message: format!("Created {}", name),
        path: Some(project.to_string_lossy().to_string()),
    })
}

#[tauri::command]
fn list_projects() -> Vec<ProjectInfo> {
    let home = dirs::home_dir().unwrap_or_default();
    let projects_dir = home.join(".rapp/projects");

    std::fs::read_dir(&projects_dir).ok()
        .map(|entries| entries.filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .map(|e| ProjectInfo {
                name: e.file_name().to_string_lossy().to_string(),
                path: e.path().to_string_lossy().to_string(),
                created: String::new(),
            }).collect())
        .unwrap_or_default()
}

#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    open::that(&path).map_err(|e| e.to_string())
}

#[tauri::command]
fn check_prerequisites() -> serde_json::Value {
    serde_json::json!({
        "python": Command::new("python3").arg("--version").output().map(|o| o.status.success()).unwrap_or(false),
        "git": Command::new("git").arg("--version").output().map(|o| o.status.success()).unwrap_or(false),
        "azure_cli": Command::new("az").arg("--version").output().map(|o| o.status.success()).unwrap_or(false),
    })
}

// ============ RAPP OS Integration ============

#[derive(Debug, Serialize, Deserialize)]
pub struct RappOsStatus {
    pub running: bool,
    pub port: u16,
    pub endpoint: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatRequest {
    pub user_input: String,
    pub user_guid: Option<String>,
    pub session_guid: Option<String>,
    pub context_guid: Option<String>,
    pub conversation_history: Option<Vec<serde_json::Value>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatResponse {
    pub response: String,
    pub voice_response: Option<String>,
    pub agent_logs: Vec<String>,
    pub agents_used: Vec<String>,
    pub session_guid: String,
    pub context_guid: String,
}

#[tauri::command]
fn start_rapp_os(state: State<RappOsState>) -> Result<RappOsStatus, String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    // Check if already running
    if let Some(ref mut child) = *process_guard {
        match child.try_wait() {
            Ok(None) => {
                // Still running
                return Ok(RappOsStatus {
                    running: true,
                    port: state.port,
                    endpoint: format!("http://127.0.0.1:{}/api/rapp", state.port),
                });
            }
            _ => {
                // Process ended, clear it
                *process_guard = None;
            }
        }
    }

    // Find rapp_os.py path
    let home = dirs::home_dir().ok_or("No home directory")?;
    let rapp_os_paths = vec![
        home.join(".rapp/rapp_os/rapp_os.py"),
        home.join("Documents/GitHub/RAPP_Desktop/rapp_os/rapp_os.py"),
        std::env::current_dir().unwrap_or_default().join("rapp_os/rapp_os.py"),
    ];

    let rapp_os_path = rapp_os_paths.iter().find(|p| p.exists());

    if rapp_os_path.is_none() {
        return Err("RAPP OS not found. Please install RAPP OS first.".to_string());
    }

    let rapp_os_path = rapp_os_path.unwrap();

    // Start RAPP OS
    let child = Command::new("python3")
        .arg(rapp_os_path)
        .arg("--port")
        .arg(state.port.to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start RAPP OS: {}", e))?;

    *process_guard = Some(child);

    // Wait a moment for server to start
    std::thread::sleep(std::time::Duration::from_millis(500));

    Ok(RappOsStatus {
        running: true,
        port: state.port,
        endpoint: format!("http://127.0.0.1:{}/api/rapp", state.port),
    })
}

#[tauri::command]
fn stop_rapp_os(state: State<RappOsState>) -> Result<RappOsStatus, String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut child) = *process_guard {
        child.kill().ok();
        child.wait().ok();
    }

    *process_guard = None;

    Ok(RappOsStatus {
        running: false,
        port: state.port,
        endpoint: String::new(),
    })
}

#[tauri::command]
fn get_rapp_os_status(state: State<RappOsState>) -> RappOsStatus {
    let process_guard = state.process.lock().ok();

    let running = process_guard.as_ref()
        .and_then(|guard| guard.as_ref())
        .and_then(|child| {
            // Can't call try_wait on immutable ref, so we check port instead
            reqwest::blocking::Client::new()
                .get(format!("http://127.0.0.1:{}/health", state.port))
                .timeout(std::time::Duration::from_millis(500))
                .send()
                .ok()
        })
        .is_some();

    RappOsStatus {
        running,
        port: state.port,
        endpoint: if running {
            format!("http://127.0.0.1:{}/api/rapp", state.port)
        } else {
            String::new()
        },
    }
}

#[tauri::command]
async fn chat_with_rapp(request: ChatRequest, state: State<'_, RappOsState>) -> Result<ChatResponse, String> {
    let endpoint = format!("http://127.0.0.1:{}/api/rapp", state.port);

    let body = serde_json::json!({
        "user_input": request.user_input,
        "user_guid": request.user_guid.unwrap_or_else(|| "desktop".to_string()),
        "session_guid": request.session_guid.unwrap_or_default(),
        "context_guid": request.context_guid.unwrap_or_else(|| "default".to_string()),
        "conversation_history": request.conversation_history.unwrap_or_default(),
    });

    let client = reqwest::Client::new();
    let response = client.post(&endpoint)
        .json(&body)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await
        .map_err(|e| format!("Failed to connect to RAPP OS: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("RAPP OS error: {}", response.status()));
    }

    response.json::<ChatResponse>()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))
}

#[tauri::command]
async fn get_agents(state: State<'_, RappOsState>) -> Result<serde_json::Value, String> {
    let endpoint = format!("http://127.0.0.1:{}/agents", state.port);

    let response = reqwest::get(&endpoint)
        .await
        .map_err(|e| format!("Failed to get agents: {}", e))?;

    response.json()
        .await
        .map_err(|e| format!("Failed to parse agents: {}", e))
}

#[tauri::command]
async fn get_contexts(state: State<'_, RappOsState>) -> Result<serde_json::Value, String> {
    let endpoint = format!("http://127.0.0.1:{}/contexts", state.port);

    let response = reqwest::get(&endpoint)
        .await
        .map_err(|e| format!("Failed to get contexts: {}", e))?;

    response.json()
        .await
        .map_err(|e| format!("Failed to parse contexts: {}", e))
}

#[tauri::command]
async fn reload_rapp_os(state: State<'_, RappOsState>) -> Result<serde_json::Value, String> {
    let endpoint = format!("http://127.0.0.1:{}/reload", state.port);

    let response = reqwest::get(&endpoint)
        .await
        .map_err(|e| format!("Failed to reload: {}", e))?;

    response.json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))
}

fn main() {
    tauri::Builder::default()
        .manage(RappOsState::default())
        .setup(|app| {
            if let Some(home) = dirs::home_dir() {
                let rapp = home.join(".rapp");
                std::fs::create_dir_all(rapp.join("agents")).ok();
                std::fs::create_dir_all(rapp.join("skills")).ok();
                std::fs::create_dir_all(rapp.join("projects")).ok();
                std::fs::create_dir_all(rapp.join("contexts")).ok();
                std::fs::create_dir_all(rapp.join("memory")).ok();
            }
            Ok(())
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event.event() {
                // Stop RAPP OS when app closes
                if let Some(state) = event.window().try_state::<RappOsState>() {
                    if let Ok(mut guard) = state.process.lock() {
                        if let Some(ref mut child) = *guard {
                            child.kill().ok();
                            child.wait().ok();
                        }
                        *guard = None;
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            // Config
            get_rapp_home, get_config, save_config,
            // Store & Hub
            fetch_manifest, install_agent, install_skill, clone_implementation,
            // Projects
            create_project, list_projects, open_path, check_prerequisites,
            // RAPP OS
            start_rapp_os, stop_rapp_os, get_rapp_os_status,
            chat_with_rapp, get_agents, get_contexts, reload_rapp_os,
        ])
        .run(tauri::generate_context!())
        .expect("error running RAPP Desktop");
}
