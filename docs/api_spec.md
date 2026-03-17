classDiagram

    class Main_API {
        <<Public API>>
        +POST /api/v1/auth/login(email, password)
        +POST /api/v1/auth/logout()
        +GET /api/v1/children()
        +GET /api/v1/stories(limit, offset)
        +POST /api/v1/stories(child_id, theme)
        +POST /api/v1/stories/:story_id()/generate_story
        +DELETE /api/v1/stories/:story_id()
        +GET /api/v1/stories/:story_id()
    }
