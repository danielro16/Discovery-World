# Discovery World Game: Product Handoff

## 1. Product Summary

This project is a **mobile-first game** whose purpose is to help users collaboratively improve real-world business data.

It is **not** the same product as the public website.

The separation is:

- **Game app**: captures contributions from players.
- **Backend**: stores proposals, evidence, visits, and consensus state.
- **Website**: reads only canonical/public business data.

The game is the data collection layer. The website is the publishing layer.

## 2. Core Goal

Turn real-world business data completion into a collaborative game loop.

Players should be able to:

- move through a real map area
- discover nearby businesses
- answer short factual questions
- upload evidence when useful
- earn progress/reputation for improving business profiles

The business data is the product outcome. The game is the interface.

## 3. Initial Geography

Start with a **small Miami Beach slice**, not the full city.

Recommended first zone:

- Ocean Drive
- Lummus Park
- South Pointe area

Reason:

- dense walkable area
- recognizable geography
- high business concentration
- easy to test proximity, discovery, and contribution flows

## 4. Product Principles

- Mobile-first from day one
- Real coordinates, real businesses
- Very short contribution tasks
- Contributions do **not** overwrite canonical business data directly
- Consensus and moderation decide what becomes public truth
- Gameplay should be useful even if visuals are simple

## 5. Recommended Stack

### Mobile App

- **React Native**
- **Expo Dev Build**
- **TypeScript**
- **MapLibre React Native**
- **Supabase Auth/Storage/Realtime** or an equivalent custom backend

Why:

- native-feeling mobile experience
- access to GPS, camera, background permissions, and push later
- map-based interaction is central
- the product is operational/data-heavy, not 3D-heavy

## 6. Why Not Build the Game as the Website

The web and the game solve different jobs:

- the website is for browsing and consuming business information
- the game is for collecting and validating business information

They should share:

- auth concepts
- place identifiers
- backend contracts
- consensus outputs

They should not share:

- UI
- navigation model
- gameplay state

## 7. Core Gameplay Loop

1. Player opens the app in Miami Beach.
2. The map shows nearby businesses with incomplete or conflicting data.
3. Player taps a business.
4. The app shows 1 to 3 micro-tasks.
5. Player answers factual questions or uploads evidence.
6. The contribution is stored as a **submission**, not as canonical truth.
7. The player receives progress, streak, or reputation updates.
8. Backend consensus eventually updates the public business profile.

## 8. Example Micro-Tasks

- Is this place open right now?
- Does it have outdoor seating?
- Is there valet parking?
- Does it accept reservations?
- Is the phone number correct?
- Is the website working?
- What is the approximate price range?

Good tasks are:

- fast
- factual
- easy to verify
- useful to the final business profile

## 9. Data Model Direction

Do **not** let the app write directly into the canonical `places` table.

Use a layered model:

### Canonical tables

- `places`
- `place_facts_public`
- `place_hours_public`
- `place_photos_public`

### Contribution tables

- `fact_questions`
- `fact_submissions`
- `photo_submissions`
- `visit_events`
- `claim_submissions`
- `moderation_queue`
- `user_reputation`

## 10. Minimum Table Responsibilities

### `places`

Canonical business record.

Suggested fields:

- `id`
- `name`
- `category`
- `address`
- `lat`
- `lng`
- `source`
- `source_license`
- `status`
- `profile_completeness`

### `fact_questions`

Definition of answerable questions.

Suggested fields:

- `id`
- `key`
- `label`
- `prompt`
- `answer_type`
- `options_json`
- `verification_rule`
- `active`

### `fact_submissions`

Raw player answers.

Suggested fields:

- `id`
- `place_id`
- `question_id`
- `user_id`
- `answer_value`
- `confidence`
- `source_type`
- `evidence_photo_id`
- `created_at`

### `visit_events`

Player presence in a real place or geofence.

Suggested fields:

- `id`
- `user_id`
- `place_id`
- `lat`
- `lng`
- `accuracy_meters`
- `visited_at`

### `user_reputation`

Trust score for weighting submissions.

Suggested fields:

- `user_id`
- `score`
- `accepted_count`
- `rejected_count`
- `flags_count`

## 11. Consensus Rule

The first version does not need machine learning.

A practical first rule:

- multiple matching submissions increase confidence
- verified photos increase confidence
- recent GPS proximity increases confidence
- higher-reputation users carry more weight
- conflicting answers go to moderation or remain unresolved

The game writes signals. The backend computes truth.

## 12. API / Backend Contract

The mobile app should need only a small set of endpoints/services:

### Read

- nearby places in map bounds
- place detail
- pending tasks for a place
- player profile and reputation

### Write

- submit fact answer
- upload photo evidence
- log visit event
- flag bad data

### Derived

- player missions
- contribution streak
- place completeness delta

## 13. MVP Scope

Build only this first:

- login
- map view
- user location
- nearby businesses
- business detail bottom sheet
- 2 to 4 micro-task types
- fact submission flow
- local progress/reputation display
- backend persistence

Do **not** start with:

- 3D world
- avatars
- crafting
- complex economies
- city-wide expansion
- social feed

## 14. Mobile UX Requirements

- bottom sheet interaction
- large touch targets
- single-thumb operation
- minimal typing
- clear distance/proximity feedback
- offline-tolerant queue if possible
- camera integration for evidence
- strong loading/error states

## 15. Suggested App Structure

```text
mobile-game/
  app/
    (tabs)/
      map.tsx
      missions.tsx
      profile.tsx
    place/[placeId].tsx
  src/
    components/
    features/
      map/
      places/
      submissions/
      missions/
      profile/
    lib/
      api/
      auth/
      location/
      storage/
    types/
```

## 16. First Screen Set

- **Map**: nearby businesses and task density
- **Place Sheet**: business detail + pending questions
- **Missions**: tasks the player can complete nearby
- **Profile**: reputation, streak, accepted contributions

## 17. Example Success Metrics

- submissions per daily active user
- accepted submissions rate
- businesses with completeness improved
- median time to complete one task
- percent of businesses with unresolved conflicts
- repeat contribution rate

## 18. Non-Goals for V1

- public editing of canonical business records
- blockchain/token mechanics
- heavy gamification before data quality works
- desktop-first design
- nationwide coverage

## 19. Build Order

1. Define backend schema and identifiers.
2. Stand up auth + place read endpoints.
3. Build mobile map with a single real Miami Beach slice.
4. Add bottom sheet and micro-task submission.
5. Store submissions and visit events.
6. Compute simple consensus.
7. Expose accepted facts to the website.

## 20. Product Statement

This is a **location-based collaborative data game**.

Its job is to transform real-world business verification into a repeatable mobile loop that produces high-quality structured data for the main web product.
