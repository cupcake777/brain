---
version: "1.0"
name: Hermes Brain Review UI
description: >
  Dark-themed admin dashboard for reviewing, approving, and syncing AI-generated
  memory proposals. Inspired by shadcn/ui token system with OKLCH color space,
  semantic naming, and layered depth. Mobile-first, dependency-free, inline CSS.
colors:
  background: "#0f1117"
  surface: "#161822"
  card: "#1c1f2e"
  card-hover: "#252840"
  border: "oklch(1 0 0 / 8%)"
  border-focus: "oklch(0.72 0.19 277)"
  ink: "#e2e4ed"
  ink-muted: "#8b90a5"
  ink-dim: "#5c6078"
  primary: "#a78bfa"
  primary-foreground: "#0f1117"
  success: "#34d399"
  success-muted: "rgba(52,211,153,.12)"
  warning: "#fbbf24"
  warning-muted: "rgba(251,191,36,.12)"
  danger: "#f87171"
  danger-muted: "rgba(248,113,113,.12)"
  info: "#67e8f9"
  info-muted: "rgba(103,232,249,.12)"
  accent: "#a78bfa"
  accent-muted: "rgba(167,139,250,.12)"
typography:
  font-family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif"
  font-mono: "'JetBrains Mono', 'Fira Code', monospace"
  heading: "1.2rem / 700 / 1.3"
  subheading: "0.95rem / 600 / 1.4"
  body: "0.9rem / 400 / 1.6"
  caption: "0.78rem / 500 / 1.4"
  micro: "0.7rem / 600 / 1.3"
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
  xl: "18px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
components:
  nav:
    background: var(--surface)
    border: "1px solid var(--border)"
    height: "56px"
    sticky: true
  card:
    background: var(--card)
    border: "1px solid var(--border)"
    rounded: lg
    hover: "border-color var(--border-focus), translateY(-2px), shadow-lg"
  badge:
    rounded: pill
    height: "22px"
    padding: "2px 10px"
    font-size: micro
  button:
    rounded: md
    height: "44px"
    hover: "opacity .85, translateY(1px) active"
    focus-ring: "3px solid var(--border-focus) / 30%"
  modal:
    overlay: "rgba(0,0,0,.6) + backdrop-blur"
    rounded: lg
    shadow: xl
    animation: "fade-in + scale-in 150ms"
  toast:
    rounded: lg
    shadow: lg
    animation: "slide-in-right 200ms, fade-out 300ms"
  input:
    rounded: md
    border: "1px solid var(--border)"
    focus: "border-color var(--border-focus), shadow ring"
---

# Hermes Brain UI Design Specification

## Overview

Dark admin dashboard for reviewing AI memory proposals. Clean, layered,
professional. Mobile-first. Zero dependencies — pure CSS + vanilla JS.

**Key characteristics:**
- Layered depth: background → surface → card (3 distinct layers)
- OKLCH-based color space for perceptual uniformity
- Smooth 150–200ms transitions everywhere
- Subtle ring focus indicators, no harsh outlines
- Pill badges, rounded-lg cards, soft shadows

## Colors

### Brand & Accents
| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | `#a78bfa` (violet-400) | Active links, CTA buttons, focus rings |
| `--success` | `#34d399` (emerald-400) | Approve actions, positive states |
| `--warning` | `#fbbf24` (amber-400) | Pending states, caution badges |
| `--danger` | `#f87171` (red-400) | Reject/delete actions, error states |
| `--info` | `#67e8f9` (cyan-300) | Informational, secondary accent |

### Surfaces (dark mode, 3-layer depth)
| Token | OKLCH | Usage |
|-------|-------|-------|
| `--bg` | `oklch(0.13 0.01 270)` | Page background |
| `--surface` | `oklch(0.16 0.01 270)` | Nav, sticky bars, elevated sections |
| `--card` | `oklch(0.20 0.02 275)` | Cards, modals, panels |

### Borders & Text
| Token | Value | Usage |
|-------|-------|-------|
| `--border` | `oklch(1 0 0 / 8%)` | Default borders (transparent white) |
| `--border-focus` | `oklch(0.72 0.19 277)` | Focus ring, accent border on active |
| `--ink` | `#e2e4ed` | Primary text |
| `--ink-muted` | `#8b90a5` | Labels, secondary text |
| `--ink-dim` | `#5c6078` | Disabled, placeholder |

## Typography

- Headings: 1.2rem/700
- Subheading: 0.95rem/600
- Body: 0.9rem/400
- Caption: 0.78rem/500
- Micro (badges, kbd): 0.7rem/600

Monospace for code, IPs, technical values.

## Elevation & Shadows

| Level | CSS | Usage |
|-------|-----|-------|
| `shadow-xs` | `0 1px 2px rgba(0,0,0,.2)` | Inputs, buttons default |
| `shadow-sm` | `0 2px 4px rgba(0,0,0,.25)` | Cards resting |
| `shadow-md` | `0 4px 12px rgba(0,0,0,.3)` | Cards hover |
| `shadow-lg` | `0 8px 24px rgba(0,0,0,.4)` | Modals, dropdowns |
| `shadow-xl` | `0 12px 40px rgba(0,0,0,.5)` | Dialog overlay |

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--r-sm` | `6px` | Inputs, kbd, small elements |
| `--r-md` | `10px` | Buttons, nav items, search |
| `--r-lg` | `14px` | Cards, panels, modals |
| `--r-xl` | `18px` | Hero cards, toast |
| `--r-pill` | `999px` | Badges, filter pills |

## Components

### Buttons
- Height: 44px (mobile), 40px (desktop)
- Hover: `opacity .85` + `translateY(-1px)`
- Active (pressed): `translateY(1px)` + shadow-xs
- Focus: `3px ring var(--border-focus) / 30%`
- Variants: approve (success bg tint), reject (danger bg tint), primary (accent bg)

### Cards
- Background: `var(--card)`
- Border: `1px solid var(--border)`
- Rounded: `var(--r-lg)`
- Shadow: `var(--shadow-sm)` → `var(--shadow-md)` on hover
- Hover: border → `var(--border-focus)`, translateY(-2px)

### Badges
- Height: 22px, pill shape
- Background: semantic color at 12% opacity
- Color: semantic color at full
- Font: micro (0.7rem/600)

### Modal / Confirm Dialog
- Overlay: `rgba(0,0,0,.6)` + `backdrop-filter: blur(4px)`
- Content: `var(--card)`, `var(--r-lg)`, `var(--shadow-xl)`
- Animation: fade-in + scale(0.95→1) 150ms ease-out

### Toast
- Position: bottom-right 20px
- Background: semantic color full
- Color: `var(--bg)` (dark)
- Rounded: `var(--r-lg)`
- Entrance: slide-in from right 200ms

### Navigation
- Sticky top, 56px height
- Background: `var(--surface)`
- Border-bottom: `1px solid var(--border)`
- Active link: `var(--border-focus)` bottom border 2px

## Responsive

| Breakpoint | Layout |
|-----------|--------|
| < 720px | Single column, hamburger nav, full-width cards |
| ≥ 720px | Multi-column grid, desktop nav links |

Touch targets: minimum 44×44px on mobile.

## Do's and Don'ts

✅ **Do:**
- Use semantic color tokens everywhere
- Add `transition: all 150ms ease` on interactive elements
- Use `var(--r-*)` for border-radius
- Use backdrop-blur on overlays
- Space sections with `var(--spacing-lg)` (24px)

❌ **Don't:**
- Never hardcode hex colors in components (use CSS vars)
- Never use `outline` (use ring focus instead)
- Never use `border-radius` magic numbers (use `var(--r-*)`)
- Never flat backgrounds — always use the 3-layer depth system