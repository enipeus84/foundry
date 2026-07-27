# Foundry Design Constitution v1.0

> **Provenance.** Migrated verbatim from the authoritative Google Doc
> `Foundry_Design_Constitution_v1.0` (Drive, last modified 2026-07-20) into
> version control on 2026-07-27, so that RFCs which cite it — RFC-004,
> RFC-004.1, RFC-004.2 — can be verified by anyone reading this repository,
> not only someone with Drive access. Content is unchanged from the source
> document; only the file's location has moved. Future revisions to the
> Design Constitution should be made here, in git, rather than in Drive.
>
> This document governs **product and visual design** decisions. It is
> distinct from the **engineering** constitutional invariants in
> [`../architecture.md`](../architecture.md#constitutional-invariants) and
> [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) — RFC reports sometimes
> refer to that pairing informally as the "Engineering Constitution." See
> [`../README.md`](../README.md) for how all of Foundry's governing
> documents relate to each other.

Foundry exists to reduce uncertainty, not increase activity. The Flight
Deck should leave users feeling calm, in control, confident and finally
curious.

## North Star

When someone opens Foundry they should feel: "Everything important is
organised and under control."

## Emotional Journey

Calm → In Control → Confident → Curious

## Core Principles

- Calm over activity.
- Mission before metrics.
- Certainty over prediction.
- Every pixel earns its place.
- Drill down, never clutter.
- Evidence behind every number.
- Secure by design.
- Accessible by default.

## Homepage Purpose

The homepage answers only three questions:

1. Am I on course?
2. Why?
3. Do I need to do anything?

## Flight Status

Use NASA terminology:

- NOMINAL
- WATCH
- OFF COURSE

## Primary KPIs

Net Worth
Liquidity
Cash Flow
Runway

## Apollo Missions

Finance should be presented as missions, not accounts:

- Mortgage Freedom
- Retirement
- Children's Future
- Legacy

## Flight Director

Present at most one evidence-backed recommendation. If no action is
required, explicitly say so.

## Recent Course Corrections

Celebrate disciplined long-term behaviours that improve mission
trajectory rather than short-term wins.

## Visual Identity

- Earthrise hero image.
- Dark restrained palette.
- Minimal animation.
- Sunrise progression through the day.
- Hidden/revealed navigation.
- Typography inspired by Apple.
- Language inspired by NASA Mission Control.

## Never on the Homepage

- Transaction feeds
- Pie charts
- Spending categories
- Market news
- Account lists
- Motivational quotes
- Widget clutter

## Engineering Principles

- Secure by Design is a standing engineering principle.
- Every UI element must trace back to evidence.
- Performance and accessibility are first-class requirements.

## Information Honesty

Every visual metaphor must faithfully represent the underlying metric.

A visually attractive representation that misstates reality is a defect,
not a design choice.

Visual status, progress, colour, direction and labels must never imply
more certainty than the underlying evidence supports.

## Mission Telemetry

Mission progress is represented as deviation from an acceptable target or
target range, not as generic percentage completion.

This allows Foundry to represent:

- higher-is-better metrics
- lower-is-better metrics
- target ranges
- binary objectives
- not-evaluable missions

through one consistent visual language.

The user must not need to understand the internal tolerance mathematics.

The visible language should remain:

- ON TARGET
- WATCH
- OFF COURSE
- WITHIN RANGE
- FROM TARGET

The picture and the policy must not be able to disagree.

## Flight Director Context

The Flight Director must explain the current Flight Plan state.

A recommendation may only be presented as a course correction when its
evidence concerns the mission causing the displayed deviation.

If no relevant course correction exists, Foundry must say so rather than
borrow unrelated advice.
