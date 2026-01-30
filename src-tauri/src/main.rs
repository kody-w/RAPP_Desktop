#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::Command;
use tauri::Manager;

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

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            if let Some(home) = dirs::home_dir() {
                let rapp = home.join(".rapp");
                std::fs::create_dir_all(rapp.join("agents")).ok();
                std::fs::create_dir_all(rapp.join("skills")).ok();
                std::fs::create_dir_all(rapp.join("projects")).ok();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_rapp_home, get_config, save_config,
            fetch_manifest, install_agent, install_skill, clone_implementation,
            create_project, list_projects, open_path, check_prerequisites,
        ])
        .run(tauri::generate_context!())
        .expect("error running RAPP Desktop");
}
