erDiagram
    USER ||--o{ CHILD : "has"
    CHILD ||--o{ STORY : "owns"

    USER {
        uuid id PK "User ID"
        string name "Parents name"
        string email "mail address(Unique)"
        string hashed_password "password"
        string subscription_plan "plan (free or premium)"
        datetime created_at "created datetime"
        datetime updated_at "updated datetime"
    }

    CHILD {
        uuid id PK "child id"
        uuid user_id FK "parents id"
        string name "child name"
        int age "child age"
        datetime created_at "created datetime"
        datetime updated_at "updated datetime"
    }

    STORY {
        uuid id PK "story id"
        uuid child_id FK "child id"
        string theme "story theme"
        string title "story title"
        text content "geterated story"
        string audio_url "audio file url"
        string status "process (generating_text, generating_audio, completed)"
        datetime created_at "created datetime"
        datetime updated_at "updated datetime"
    }