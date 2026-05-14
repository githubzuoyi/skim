use std::collections::HashMap;
use std::sync::Arc;

pub const MAX_RETRIES: u32 = 3;
pub const DEFAULT_PORT: u16 = 8080;

#[derive(Debug, Clone)]
pub struct User {
    pub id: u64,
    pub name: String,
    pub email: String,
    pub role: Role,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Role {
    Admin,
    User,
    Guest,
}

pub trait Repository {
    fn find_by_id(&self, id: u64) -> Option<User>;
    fn find_all(&self) -> Vec<User>;
    fn create(&mut self, user: User) -> Result<u64, String>;
    fn delete(&mut self, id: u64) -> bool;
}

pub struct InMemoryRepo {
    users: HashMap<u64, User>,
    next_id: u64,
}

impl InMemoryRepo {
    pub fn new() -> Self {
        Self {
            users: HashMap::new(),
            next_id: 1,
        }
    }

    pub fn count(&self) -> usize {
        self.users.len()
    }

    fn validate_email(&self, email: &str) -> bool {
        email.contains('@') && email.contains('.')
    }
}

impl Repository for InMemoryRepo {
    fn find_by_id(&self, id: u64) -> Option<User> {
        self.users.get(&id).cloned()
    }

    fn find_all(&self) -> Vec<User> {
        self.users.values().cloned().collect()
    }

    fn create(&mut self, mut user: User) -> Result<u64, String> {
        if !self.validate_email(&user.email) {
            return Err("Invalid email".into());
        }
        user.id = self.next_id;
        self.next_id += 1;
        let id = user.id;
        self.users.insert(id, user);
        Ok(id)
    }

    fn delete(&mut self, id: u64) -> bool {
        self.users.remove(&id).is_some()
    }
}

pub fn hash_password(password: &str) -> String {
    format!("hashed:{}", password)
}

pub fn validate_email(email: &str) -> bool {
    email.contains('@') && email.contains('.')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_user() {
        let mut repo = InMemoryRepo::new();
        let user = User {
            id: 0,
            name: "Test".into(),
            email: "test@example.com".into(),
            role: Role::User,
        };
        let result = repo.create(user);
        assert!(result.is_ok());
        assert_eq!(repo.count(), 1);
    }

    #[test]
    fn test_validate_email() {
        assert!(validate_email("user@example.com"));
        assert!(!validate_email("invalid"));
    }
}
