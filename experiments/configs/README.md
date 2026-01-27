# ABM Experiment Configuration Contract

This document defines the structure and requirements for configuration files used in agent-based modeling (ABM) experiments within this project. It establishes a clear contract to ensure that simulations are described precisely, reproducibly, and in a manner that facilitates scientific rigor and transparency.

## Required Fields

Configuration files must include the following fields, organized into thematic groups:

### Experiment Metadata

- **experiment_name**: A unique identifier for the experiment.
- **description**: A concise summary of the experiment’s purpose and hypotheses.
- **author**: Name(s) of the experimenter(s) or responsible party.
- **date_created**: Date the configuration was authored or last modified.

### World Structure

- **num_patches**: Integer specifying the number of spatial patches or locations in the simulation.
- **population_sizes**: Mapping of agent types to their initial population counts per patch or globally.
- **environmental_parameters**: Optional parameters defining static or dynamic environmental conditions.

### Seasonality

- **seasonal_period**: Integer denoting the length of the seasonal cycle in simulation steps.
- **phase_offsets**: Mapping of relevant entities or processes to phase offset values within the seasonal cycle.
- **forcing_amplitudes**: Magnitudes of seasonal forcing applied to environmental or agent-level variables.
- **forcing_sign**: Directionality of forcing (e.g., positive or negative influence).

### Authority & Power Parameters

- **violence_factor**: Numeric parameter controlling the intensity or likelihood of violent interactions.
- **information_spread_rate**: Rate at which information propagates through the agent population.
- **charisma_levels**: Mapping of agent types or classes to charisma or influence scores.
- **memory_decay**: Parameter defining how agent memory or past influence diminishes over time.
- **lock_in_effects**: Boolean or parameter indicating persistence of power structures or agent states.

### Runtime & Reproducibility

- **total_steps**: Total number of simulation steps to execute.
- **burn_in_period**: Number of initial steps to exclude from analysis to allow system stabilization.
- **random_seed**: Integer seed for all stochastic processes to ensure reproducibility.
- **logging_frequency**: Interval at which simulation state or metrics are recorded.

### Observation

- **metrics_to_log**: List of variables or agent attributes to record during simulation.
- **aggregation_windows**: Definitions of temporal windows over which logged metrics should be aggregated (e.g., moving averages, cumulative sums).

## Stop Condition

Configurations must be self-contained descriptions of the simulation experiment and should not reference concepts related to training, learning, or optimization. The focus is on defining the initial conditions, parameters, and runtime behavior of the agent-based simulation itself.

## Example YAML Schema

```yaml
experiment_name:
description:
author:
date_created:

world_structure:
  num_patches:
  population_sizes:
    agent_type_1:
    agent_type_2:
  environmental_parameters:

seasonality:
  seasonal_period:
  phase_offsets:
    process_1:
    process_2:
  forcing_amplitudes:
    variable_1:
    variable_2:
  forcing_sign:

authority_and_power:
  violence_factor:
  information_spread_rate:
  charisma_levels:
    agent_type_1:
    agent_type_2:
  memory_decay:
  lock_in_effects:

runtime_and_reproducibility:
  total_steps:
  burn_in_period:
  random_seed:
  logging_frequency:

observation:
  metrics_to_log:
    - 
  aggregation_windows:
    - 
```
