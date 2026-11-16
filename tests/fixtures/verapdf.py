# SPDX-License-Identifier: AGPL-3.0-only
"""Reviewed validator XML examples shared by transport and composition controls."""

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<report>
  <buildInformation>
    <releaseDetails id="core" version="9.9.9" buildDate="x"></releaseDetails>
  </buildInformation>
  <jobs><job>
    <validationReport jobEndStatus="{status}" profileName="PDF/UA-1 validation profile"
        isCompliant="{compliant}">
      <details passedRules="1" failedRules="{failed}">
        {rules}
      </details>
    </validationReport>
  </job></jobs>
</report>"""
FAILED_RULE = """<rule specification="ISO 14289-1:2014" clause="7.1" testNumber="10"
    status="failed" failedChecks="4">
  <description>The catalog shall include DisplayDocTitle.</description>
  <check status="failed"><context>root/a</context><errorMessage>one</errorMessage></check>
  <check status="failed"><context>root/b</context><errorMessage>two</errorMessage></check>
  <check status="failed"><context>root/c</context><errorMessage>three</errorMessage></check>
  <check status="failed"><context>root/d</context><errorMessage>four</errorMessage></check>
</rule>
<rule specification="ISO 14289-1:2014" clause="6.2" testNumber="1" status="passed"
    failedChecks="0"><description>Fine.</description></rule>"""
