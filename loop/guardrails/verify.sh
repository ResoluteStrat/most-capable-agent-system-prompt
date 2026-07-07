#!/usr/bin/env bash
set -e
npm run typecheck --if-present
npm test --if-present
npm run lint --if-present
