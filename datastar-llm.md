# Guide

# Getting Started

Datastar simplifies frontend development, allowing you to build backend-driven, interactive UIs using a hypermedia-first approach that extends and enhances HTML.

Datastar provides backend reactivity like htmx and frontend reactivity like Alpine.js in a lightweight frontend framework that doesn’t require any npm packages or other dependencies. It provides two primary functions:

1. Modify the DOM and state by sending events from your backend.
2. Build reactivity into your frontend using standard `data-*` HTML attributes.

> Other useful resources include an AI-generated deep wiki, LLM-ingestible code samples, and single-page docs.

## Installation

The quickest way to use Datastar is to include it using a `script` tag that fetches it from a CDN.

```
<script type="module" src="https://cdn.jsdelivr.net/gh/starfederation/[email protected]/bundles/datastar.js"></script>
```

If you prefer to host the file yourself, download the script or create your own bundle using the bundler, then include it from the appropriate path.

```
<script type="module" src="/path/to/datastar.js"></script>
```

To import Datastar using a package manager such as npm, Deno, or Bun, you can use an import statement.

```
// @ts-expect-error (only required for TypeScript projects)
import 'https://cdn.jsdelivr.net/gh/starfederation/[email protected]/bundles/datastar.js'
```

## `data-*`

At the core of Datastar are `data-*` HTML attributes (hence the name). They allow you to add reactivity to your frontend and interact with your backend in a declarative way.

> The Datastar VSCode extension and IntelliJ plugin provide autocompletion for all available `data-*` attributes.

The `data-on` attribute can be used to attach an event listener to an element and execute an expression whenever the event is triggered. The value of the attribute is a Datastar expression in which JavaScript can be used.

```
<button data-on:click="alert('I’m sorry, Dave. I’m afraid I can’t do that.')">
    Open the pod bay doors, HAL.
</button>
```

Demo

Open the pod bay doors, HAL.

We’ll explore more data attributes in the next section of the guide.

## Patching Elements

With Datastar, the backend *drives* the frontend by **patching** (adding, updating and removing) HTML elements in the DOM.

Datastar receives elements from the backend and manipulates the DOM using a morphing strategy (by default). Morphing ensures that only modified parts of the DOM are updated, preserving state and improving performance.

Datastar provides actions for sending requests to the backend. The `@get()` action sends a `GET` request to the provided URL using a fetch request.

```
<button data-on:click="@get('/endpoint')">
    Open the pod bay doors, HAL.
</button>
<div id="hal"></div>
```

> Actions in Datastar are helper functions that have the syntax `@actionName()`. Read more about actions in the reference.

If the response has a `content-type` of `text/html`, the top-level HTML elements will be morphed into the existing DOM based on the element IDs.

```
<div id="hal">
    I’m sorry, Dave. I’m afraid I can’t do that.
</div>
```

We call this a “Patch Elements” event because multiple elements can be patched into the DOM at once.

Demo

Open the pod bay doors, HAL. `Waiting for an order...`

In the example above, the DOM must contain an element with a `hal` ID in order for morphing to work. Other patching strategies are available, but morph is the best and simplest choice in most scenarios.

If the response has a `content-type` of `text/event-stream`, it can contain zero or more SSE events. The example above can be replicated using a `datastar-patch-elements` SSE event.

```
event: datastar-patch-elements
data: elements <div id="hal">
data: elements     I’m sorry, Dave. I’m afraid I can’t do that.
data: elements </div>

```

Because we can send as many events as we want in a stream, and because it can be a long-lived connection, we can extend the example above to first send HAL’s response and then, after a few seconds, reset the text.

```
event: datastar-patch-elements
data: elements <div id="hal">
data: elements     I’m sorry, Dave. I’m afraid I can’t do that.
data: elements </div>

event: datastar-patch-elements
data: elements <div id="hal">
data: elements     Waiting for an order...
data: elements </div>

```

Demo

Open the pod bay doors, HAL. `Waiting for an order...`

Here’s the code to generate the SSE events above using the SDKs.

```
;; Import the SDK's api and your adapter
(require
 '[starfederation.datastar.clojure.api :as d*]
 '[starfederation.datastar.clojure.adapter.http-kit :refer [->sse-response on-open]])

;; in a ring handler
(defn handler [request]
  ;; Create an SSE response
  (->sse-response request
                  {on-open
                   (fn [sse]
                     ;; Patches elements into the DOM
                     (d*/patch-elements! sse
                                         "<div id=\"hal\">I’m sorry, Dave. I’m afraid I can’t do that.</div>")
                     (Thread/sleep 1000)
                     (d*/patch-elements! sse
                                         "<div id=\"hal\">Waiting for an order...</div>"))}))
```

```
using StarFederation.Datastar.DependencyInjection;

// Adds Datastar as a service
builder.Services.AddDatastar();

app.MapGet("/", async (IDatastarService datastarService) =>
{
    // Patches elements into the DOM.
    await datastarService.PatchElementsAsync(@"<div id=""hal"">I’m sorry, Dave. I’m afraid I can’t do that.</div>");

    await Task.Delay(TimeSpan.FromSeconds(1));

    await datastarService.PatchElementsAsync(@"<div id=""hal"">Waiting for an order...</div>");
});
```

```
import (
    "github.com/starfederation/datastar-go/datastar"
    time
)

// Creates a new `ServerSentEventGenerator` instance.
sse := datastar.NewSSE(w,r)

// Patches elements into the DOM.
sse.PatchElements(
    `<div id="hal">I’m sorry, Dave. I’m afraid I can’t do that.</div>`
)

time.Sleep(1 * time.Second)

sse.PatchElements(
    `<div id="hal">Waiting for an order...</div>`
)
```

```
import starfederation.datastar.utils.ServerSentEventGenerator;

// Creates a new `ServerSentEventGenerator` instance.
AbstractResponseAdapter responseAdapter = new HttpServletResponseAdapter(response);
ServerSentEventGenerator generator = new ServerSentEventGenerator(responseAdapter);

// Patches elements into the DOM.
generator.send(PatchElements.builder()
    .data("<div id=\"hal\">I’m sorry, Dave. I’m afraid I can’t do that.</div>")
    .build()
);

Thread.sleep(1000);

generator.send(PatchElements.builder()
    .data("<div id=\"hal\">Waiting for an order...</div>")
    .build()
);
```

```
val generator = ServerSentEventGenerator(response)

generator.patchElements(
    elements = """<div id="hal">I’m sorry, Dave. I’m afraid I can’t do that.</div>""",
)

Thread.sleep(ONE_SECOND)

generator.patchElements(
    elements = """<div id="hal">Waiting for an order...</div>""",
)
```

```
use starfederation\datastar\ServerSentEventGenerator;

// Creates a new `ServerSentEventGenerator` instance.
$sse = new ServerSentEventGenerator();

// Patches elements into the DOM.
$sse->patchElements(
    '<div id="hal">I’m sorry, Dave. I’m afraid I can’t do that.</div>'
);

sleep(1);

$sse->patchElements(
    '<div id="hal">Waiting for an order...</div>'
);
```

```
from datastar_py import ServerSentEventGenerator as SSE
from datastar_py.sanic import datastar_response

@app.get('/open-the-bay-doors')
@datastar_response
async def open_doors(request):
    yield SSE.patch_elements('<div id="hal">I’m sorry, Dave. I’m afraid I can’t do that.</div>')
    await asyncio.sleep(1)
    yield SSE.patch_elements('<div id="hal">Waiting for an order...</div>')
```

```
require 'datastar'

# Create a Datastar::Dispatcher instance

datastar = Datastar.new(request:, response:)

# In a Rack handler, you can instantiate from the Rack env
# datastar = Datastar.from_rack_env(env)

# Start a streaming response
datastar.stream do |sse|
  # Patches elements into the DOM.
  sse.patch_elements %(<div id="hal">I’m sorry, Dave. I’m afraid I can’t do that.</div>)

  sleep 1
  
  sse.patch_elements %(<div id="hal">Waiting for an order...</div>)
end
```

```
use async_stream::stream;
use datastar::prelude::*;
use std::thread;
use std::time::Duration;

Sse(stream! {
    // Patches elements into the DOM.
    yield PatchElements::new("<div id='hal'>I’m sorry, Dave. I’m afraid I can’t do that.</div>").into();

    thread::sleep(Duration::from_secs(1));
    
    yield PatchElements::new("<div id='hal'>Waiting for an order...</div>").into();
})
```

```
// Creates a new `ServerSentEventGenerator` instance (this also sends required headers)
ServerSentEventGenerator.stream(req, res, (stream) => {
    // Patches elements into the DOM.
    stream.patchElements(`<div id="hal">I’m sorry, Dave. I’m afraid I can’t do that.</div>`);

    setTimeout(() => {
        stream.patchElements(`<div id="hal">Waiting for an order...</div>`);
    }, 1000);
});
```

> In addition to your browser’s dev tools, the Datastar Inspector can be used to monitor and inspect SSE events received by Datastar.

We’ll cover event streams and SSE events in more detail later in the guide, but as you can see, they are just plain text events with a special syntax, made simpler by the SDKs.

# Reactive Signals

In a hypermedia approach, the backend drives state to the frontend and acts as the primary source of truth. It’s up to the backend to determine what actions the user can take next by patching appropriate elements in the DOM.

Sometimes, however, you may need access to frontend state that’s driven by user interactions. Click, input and keydown events are some of the more common user events that you’ll want your frontend to be able to react to.

Datastar uses *signals* to manage frontend state. You can think of signals as reactive variables that automatically track and propagate changes in and to Datastar expressions. Signals are denoted using the `$` prefix.

## Data Attributes

Datastar allows you to add reactivity to your frontend and interact with your backend in a declarative way using data-* attributes.

> The Datastar VSCode extension and IntelliJ plugin provide autocompletion for all available `data-*` attributes.

### `data-bind`

The `data-bind` attribute sets up two-way data binding on any HTML element that receives user input or selections. These include `input`, `textarea`, `select`, `checkbox` and `radio` elements, as well as web components whose value can be made reactive.

```
<input data-bind:foo />
```

This creates a new signal that can be called using `$foo`, and binds it to the element’s value. If either is changed, the other automatically updates.

You can accomplish the same thing passing the signal name as a *value*, an alternate syntax that might be more useful for some templating languages:

```
<input data-bind="foo" />
```

### `data-text`

The `data-text` attribute sets the text content of an element to the value of a signal. The `$` prefix is required to denote a signal.

```
<input data-bind:foo />
<div data-text="$foo"></div>
```

Demo

```

```

The value of the `data-text` attribute is a Datastar expression that is evaluated, meaning that we can use JavaScript in it.

```
<input data-bind:foo />
<div data-text="$foo.toUpperCase()"></div>
```

Demo

```

```

### `data-computed`

The `data-computed` attribute creates a new signal that is derived from a reactive expression. The computed signal is read-only, and its value is automatically updated when any signals in the expression are updated.

```
<input data-bind:foo />
<div data-computed:repeated="$foo.repeat(2)" data-text="$repeated"></div>
```

This results in the `$repeated` signal’s value always being equal to the value of the `$foo` signal repeated twice. Computed signals are useful for memoizing expressions containing other signals.

Demo

```

```

### `data-show`

The `data-show` attribute can be used to show or hide an element based on whether an expression evaluates to `true` or `false`.

```
<input data-bind:foo />
<button data-show="$foo != ''">
    Save
</button>
```

This results in the button being visible only when the input value is *not* an empty string. This could also be shortened to `data-show="$foo"`.

Demo

Save

Since the button is visible until Datastar processes the `data-show` attribute, it’s a good idea to set its initial style to `display: none;` to prevent a flash of unwanted content.

```
<input data-bind:foo />
<button data-show="$foo != ''" style="display: none;">
    Save
</button>
```

### `data-class`

The `data-class` attribute allows us to add or remove an element’s class based on an expression.

```
<input data-bind:foo />
<button data-class:success="$foo != ''">
    Save
</button>
```

If the expression evaluates to `true`, the `success` class is added to the element; otherwise, it is removed.

Demo

Save

The `data-class` attribute can also be used to add or remove multiple classes from an element using a set of key-value pairs, where the keys represent class names and the values represent expressions.

```
<button data-class="{success: $foo != '', 'font-bold': $foo == 'bar'}">
    Save
</button>
```

### `data-attr`

The `data-attr` attribute can be used to bind the value of any HTML attribute to an expression.

```
<input data-bind:foo />
<button data-attr:disabled="$foo == ''">
    Save
</button>
```

This results in a `disabled` attribute being given the value `true` whenever the input is an empty string.

Demo

Save

The `data-attr` attribute can also be used to set the values of multiple attributes on an element using a set of key-value pairs, where the keys represent attribute names and the values represent expressions.

```
<button data-attr="{disabled: $foo == '', title: $foo}">Save</button>
```

### `data-signals`

Signals are globally accessible from anywhere in the DOM. So far, we’ve created signals on the fly using `data-bind` and `data-computed`. If a signal is used without having been created, it will be created automatically and its value set to an empty string.

Another way to create signals is using the `data-signals` attribute, which patches (adds, updates or removes) one or more signals into the existing signals.

```
<div data-signals:foo="1"></div>
```

Signals can be nested using dot-notation.

```
<div data-signals:form.foo="2"></div>
```

The `data-signals` attribute can also be used to patch multiple signals using a set of key-value pairs, where the keys represent signal names and the values represent expressions.

```
<div data-signals="{foo: 1, form: {foo: 2}}"></div>
```

### `data-on`

The `data-on` attribute can be used to attach an event listener to an element and run an expression whenever the event is triggered.

```
<input data-bind:foo />
<button data-on:click="$foo = ''">
    Reset
</button>
```

This results in the `$foo` signal’s value being set to an empty string whenever the button element is clicked. This can be used with any valid event name such as `data-on:keydown`, `data-on:mouseover`, etc. Custom events may also be used.

Demo

Reset

These are just *some* of the attributes available in Datastar. For a complete list, see the attribute reference.

## Frontend Reactivity

Datastar’s data attributes enable declarative signals and expressions, providing a simple yet powerful way to add reactivity to the frontend.

Datastar expressions are strings that are evaluated by Datastar attributes and actions. While they are similar to JavaScript, there are some important differences that are explained in the next section of the guide.

```
<div data-signals:hal="'...'">
    <button data-on:click="$hal = 'Affirmative, Dave. I read you.'">
        HAL, do you read me?
    </button>
    <div data-text="$hal"></div>
</div>
```

Demo

HAL, do you read me?

```

```

See if you can figure out what the code below does based on what you’ve learned so far, *before* trying the demo below it.

```
<div
    data-signals="{response: '', answer: 'bread'}"
    data-computed:correct="$response.toLowerCase() == $answer"
>
    <div id="question">What do you put in a toaster?</div>
    <button data-on:click="$response = prompt('Answer:') ?? ''">BUZZ</button>
    <div data-show="$response != ''">
        You answered “<span data-text="$response"></span>”.
        <span data-show="$correct">That is correct ✅</span>
        <span data-show="!$correct">
        The correct answer is “
        <span data-text="$answer"></span>
        ” 🤷
        </span>
    </div>
</div>
```

Demo

What do you put in a toaster?

BUZZ

You answered “”. That is correct ✅ The correct answer is “bread” 🤷

> The Datastar Inspector can be used to inspect and filter current signals and view signal patch events in real-time.

## Patching Signals

Remember that in a hypermedia approach, the backend drives state to the frontend. Just like with elements, frontend signals can be **patched** (added, updated and removed) from the backend using backend actions.

```
<div data-signals:hal="'...'">
    <button data-on:click="@get('/endpoint')">
        HAL, do you read me?
    </button>
    <div data-text="$hal"></div>
</div>
```

If a response has a `content-type` of `application/json`, the signal values are patched into the frontend signals.

We call this a “Patch Signals” event because multiple signals can be patched (using JSON Merge Patch RFC 7396) into the existing signals.

```
{"hal": "Affirmative, Dave. I read you."}
```

Demo

HAL, do you read me?

Reset

If the response has a `content-type` of `text/event-stream`, it can contain zero or more SSE events. The example above can be replicated using a `datastar-patch-signals` SSE event.

```
event: datastar-patch-signals
data: signals {hal: 'Affirmative, Dave. I read you.'}

```

Because we can send as many events as we want in a stream, and because it can be a long-lived connection, we can extend the example above to first set the `hal` signal to an “affirmative” response and then, after a second, reset the signal.

```
event: datastar-patch-signals
data: signals {hal: 'Affirmative, Dave. I read you.'}

// Wait 1 second

event: datastar-patch-signals
data: signals {hal: '...'}

```

Demo

HAL, do you read me?

Here’s the code to generate the SSE events above using the SDKs.

```
;; Import the SDK's api and your adapter
(require
  '[starfederation.datastar.clojure.api :as d*]
  '[starfederation.datastar.clojure.adapter.http-kit :refer [->sse-response on-open]])

;; in a ring handler
(defn handler [request]
  ;; Create an SSE response
  (->sse-response request
                  {on-open
                   (fn [sse]
                     ;; Patches signal.
                     (d*/patch-signals! sse "{hal: 'Affirmative, Dave. I read you.'}")
                     (Thread/sleep 1000)
                     (d*/patch-signals! sse "{hal: '...'}"))}))
```

```
using StarFederation.Datastar.DependencyInjection;

// Adds Datastar as a service
builder.Services.AddDatastar();

app.MapGet("/hal", async (IDatastarService datastarService) =>
{
    // Patches signals.
    await datastarService.PatchSignalsAsync(new { hal = "Affirmative, Dave. I read you" });

    await Task.Delay(TimeSpan.FromSeconds(3));

    await datastarService.PatchSignalsAsync(new { hal = "..." });
});
```

```
import (
    "github.com/starfederation/datastar-go/datastar"
)

// Creates a new `ServerSentEventGenerator` instance.
sse := datastar.NewSSE(w, r)

// Patches signals
sse.PatchSignals([]byte(`{hal: 'Affirmative, Dave. I read you.'}`))

time.Sleep(1 * time.Second)

sse.PatchSignals([]byte(`{hal: '...'}`))
```

```
import starfederation.datastar.utils.ServerSentEventGenerator;

// Creates a new `ServerSentEventGenerator` instance.
AbstractResponseAdapter responseAdapter = new HttpServletResponseAdapter(response);
ServerSentEventGenerator generator = new ServerSentEventGenerator(responseAdapter);

// Patches signals.
generator.send(PatchSignals.builder()
    .data("{\"hal\": \"Affirmative, Dave. I read you.\"}")
    .build()
);

Thread.sleep(1000);

generator.send(PatchSignals.builder()
    .data("{\"hal\": \"...\"}")
    .build()
);
```

```
val generator = ServerSentEventGenerator(response)

generator.patchSignals(
    signals = """{"hal": "Affirmative, Dave. I read you."}""",
)

Thread.sleep(ONE_SECOND)

generator.patchSignals(
    signals = """{"hal": "..."}""",
)
```

```
use starfederation\datastar\ServerSentEventGenerator;

// Creates a new `ServerSentEventGenerator` instance.
$sse = new ServerSentEventGenerator();

// Patches signals.
$sse->patchSignals(['hal' => 'Affirmative, Dave. I read you.']);

sleep(1);

$sse->patchSignals(['hal' => '...']);
```

```
from datastar_py import ServerSentEventGenerator as SSE
from datastar_py.sanic import datastar_response

@app.get('/do-you-read-me')
@datastar_response
async def open_doors(request):
    yield SSE.patch_signals({"hal": "Affirmative, Dave. I read you."})
    await asyncio.sleep(1)
    yield SSE.patch_signals({"hal": "..."})
```

```
require 'datastar'

# Create a Datastar::Dispatcher instance

datastar = Datastar.new(request:, response:)

# In a Rack handler, you can instantiate from the Rack env
# datastar = Datastar.from_rack_env(env)

# Start a streaming response
datastar.stream do |sse|
  # Patches signals
  sse.patch_signals(hal: 'Affirmative, Dave. I read you.')

  sleep 1
  
  sse.patch_signals(hal: '...')
end
```

```
use async_stream::stream;
use datastar::prelude::*;
use std::thread;
use std::time::Duration;

Sse(stream! {
    // Patches signals.
    yield PatchSignals::new("{hal: 'Affirmative, Dave. I read you.'}").into();

    thread::sleep(Duration::from_secs(1));
    
    yield PatchSignals::new("{hal: '...'}").into();
})
```

```
// Creates a new `ServerSentEventGenerator` instance (this also sends required headers)
ServerSentEventGenerator.stream(req, res, (stream) => {
    // Patches signals.
    stream.patchSignals({'hal': 'Affirmative, Dave. I read you.'});

    setTimeout(() => {
        stream.patchSignals({'hal': '...'});
    }, 1000);
});
```

> In addition to your browser’s dev tools, the Datastar Inspector can be used to monitor and inspect SSE events received by Datastar.

We’ll cover event streams and SSE events in more detail later in the guide, but as you can see, they are just plain text events with a special syntax, made simpler by the SDKs.

# Datastar Expressions

Datastar expressions are strings that are evaluated by `data-*` attributes. While they are similar to JavaScript, there are some important differences that make them more powerful for declarative hypermedia applications.

## Datastar Expressions

The following example outputs `1` because we’ve defined `foo` as a signal with the initial value `1`, and are using `$foo` in a `data-*` attribute.

```
<div data-signals:foo="1">
    <div data-text="$foo"></div>
</div>
```

A variable `el` is available in every Datastar expression, representing the element that the attribute is attached to.

```
<div id="foo" data-text="el.id"></div>
```

When Datastar evaluates the expression `$foo`, it first converts it to the signal value, and then evaluates that expression in a sandboxed context. This means that JavaScript can be used in Datastar expressions.

```
<div data-text="$foo.length"></div>
```

JavaScript operators are also available in Datastar expressions. This includes (but is not limited to) the ternary operator `?:`, the logical OR operator `||`, and the logical AND operator `&&`. These operators are helpful in keeping Datastar expressions terse.

```
// Output one of two values, depending on the truthiness of a signal
<div data-text="$landingGearRetracted ? 'Ready' : 'Waiting'"></div>

// Show a countdown if the signal is truthy or the time remaining is less than 10 seconds
<div data-show="$landingGearRetracted || $timeRemaining < 10">
    Countdown
</div>

// Only send a request if the signal is truthy
<button data-on:click="$landingGearRetracted && @post('/launch')">
    Launch
</button>
```

Multiple statements can be used in a single expression by separating them with a semicolon.

```
<div data-signals:foo="1">
    <button data-on:click="$landingGearRetracted = true; @post('/launch')">
        Force launch
    </button>
</div>
```

Expressions may span multiple lines, but a semicolon must be used to separate statements. Unlike JavaScript, line breaks alone are not sufficient to separate statements.

```
<div data-signals:foo="1">
    <button data-on:click="
        $landingGearRetracted = true; 
        @post('/launch')
    ">
        Force launch
    </button>
</div>
```

## Using JavaScript

Most of your JavaScript logic should go in `data-*` attributes, since reactive signals and actions only work in Datastar expressions.

> Caution: if you find yourself trying to do too much in Datastar expressions, **you are probably overcomplicating it™**.

Any additional JavaScript functionality you require that cannot belong in `data-*` attributes should be extracted out into external scripts or, better yet, web components.

> Always encapsulate state and send **props down, events up**.

### External Scripts

When using external scripts, pass data into functions via arguments and return a result *or* listen for custom events dispatched from them **props down, events up**.

In this way, the function is encapsulated – all it knows is that it receives input via an argument, acts on it, and optionally returns a result or dispatches a custom event – and `data-*` attributes can be used to drive reactivity.

```
<div data-signals:result>
    <input data-bind:foo 
        data-on:input="$result = myfunction($foo)"
    >
    <span data-text="$result"></span>
</div>
```

```
function myfunction(data) {
    return `You entered: ${data}`;
}
```

If your function call is asynchronous then it will need to dispatch a custom event containing the result. While asynchronous code *can* be placed within Datastar expressions, Datastar will *not* await it.

```
<div data-signals:result>
    <input data-bind:foo 
           data-on:input="myfunction(el, $foo)"
           data-on:mycustomevent__window="$result = evt.detail.value"
    >
    <span data-text="$result"></span>
</div>
```

```
async function myfunction(element, data) {
    const value = await new Promise((resolve) => {
        setTimeout(() => resolve(`You entered: ${data}`), 1000);
    });
    element.dispatchEvent(
        new CustomEvent('mycustomevent', {detail: {value}})
    );
}
```

See the sortable example.

### Web Components

Web components allow you create reusable, encapsulated, custom elements. They are native to the web and require no external libraries or frameworks. Web components unlock custom elements – HTML tags with custom behavior and styling.

When using web components, pass data into them via attributes and listen for custom events dispatched from them (*props down, events up*).

In this way, the web component is encapsulated – all it knows is that it receives input via an attribute, acts on it, and optionally dispatches a custom event containing the result – and `data-*` attributes can be used to drive reactivity.

```
<div data-signals:result="''">
    <input data-bind:foo />
    <my-component
        data-attr:src="$foo"
        data-on:mycustomevent="$result = evt.detail.value"
    ></my-component>
    <span data-text="$result"></span>
</div>
```

```
class MyComponent extends HTMLElement {
    static get observedAttributes() {
        return ['src'];
    }

    attributeChangedCallback(name, oldValue, newValue) {
        const value = `You entered: ${newValue}`;
        this.dispatchEvent(
            new CustomEvent('mycustomevent', {detail: {value}})
        );
    }
}

customElements.define('my-component', MyComponent);
```

Since the `value` attribute is allowed on web components, it is also possible to use `data-bind` to bind a signal to the web component’s value. Note that a `change` event must be dispatched so that the event listener used by `data-bind` is triggered by the value change.

See the web component example.

## Executing Scripts

Just like elements and signals, the backend can also send JavaScript to be executed on the frontend using backend actions.

```
<button data-on:click="@get('/endpoint')">
    What are you talking about, HAL?
</button>
```

If a response has a `content-type` of `text/javascript`, the value will be executed as JavaScript in the browser.

```
alert('This mission is too important for me to allow you to jeopardize it.')
```

Demo

What are you talking about, HAL?

If the response has a `content-type` of `text/event-stream`, it can contain zero or more SSE events. The example above can be replicated by including a `script` tag inside of a `datastar-patch-elements` SSE event.

```
event: datastar-patch-elements
data: elements <div id="hal">
data: elements     <script>alert('This mission is too important for me to allow you to jeopardize it.')</script>
data: elements </div>

```

If you *only* want to execute a script, you can `append` the script tag to the `body`.

```
event: datastar-patch-elements
data: mode append
data: selector body
data: elements <script>alert('This mission is too important for me to allow you to jeopardize it.')</script>

```

Most SDKs have an `ExecuteScript` helper function for executing a script. Here’s the code to generate the SSE event above using the Go SDK.

```
sse := datastar.NewSSE(writer, request)
sse.ExecuteScript(`alert('This mission is too important for me to allow you to jeopardize it.')`)
```

Demo

What are you talking about, HAL?

We’ll cover event streams and SSE events in more detail later in the guide, but as you can see, they are just plain text events with a special syntax, made simpler by the SDKs.

# Backend Requests

Between attributes and actions, Datastar provides you with everything you need to build hypermedia-driven applications. Using this approach, the backend drives state to the frontend and acts as the single source of truth, determining what actions the user can take next.

## Sending Signals

By default, all signals (except for local signals whose keys begin with an underscore) are sent in an object with every backend request. When using a `GET` request, the signals are sent as a `datastar` query parameter, otherwise they are sent as a JSON body.

By sending **all** signals in every request, the backend has full access to the frontend state. This is by design. It is **not** recommended to send partial signals, but if you must, you can use the `filterSignals` option to filter the signals sent to the backend.

### Nesting Signals

Signals can be nested, making it easier to target signals in a more granular way on the backend.

Using dot-notation:

```
<div data-signals:foo.bar="1"></div>
```

Using object syntax:

```
<div data-signals="{foo: {bar: 1}}"></div>
```

Using two-way binding:

```
<input data-bind:foo.bar />
```

A practical use-case of nested signals is when you have repetition of state on a page. The following example tracks the open/closed state of a menu on both desktop and mobile devices, and the toggleAll() action to toggle the state of all menus at once.

```
<div data-signals="{menu: {isOpen: {desktop: false, mobile: false}}}">
    <button data-on:click="@toggleAll({include: /^menu\.isOpen\./})">
        Open/close menu
    </button>
</div>
```

## Reading Signals

To read signals from the backend, JSON decode the `datastar` query param for `GET` requests, and the request body for all other methods.

All SDKs provide a helper function to read signals. Here’s how you would read the nested signal `foo.bar` from an incoming request.

No example found for Clojure

```
using StarFederation.Datastar.DependencyInjection;

// Adds Datastar as a service
builder.Services.AddDatastar();

public record Signals
{
    [JsonPropertyName("foo")] [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public FooSignals? Foo { get; set; } = null;

    public record FooSignals
    {
        [JsonPropertyName("bar")] [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
        public string? Bar { get; set; }
    }
}

app.MapGet("/read-signals", async (IDatastarService datastarService) =>
{
    Signals? mySignals = await datastarService.ReadSignalsAsync<Signals>();
    var bar = mySignals?.Foo?.Bar;
});
```

```
import ("github.com/starfederation/datastar-go/datastar")

type Signals struct {
    Foo struct {
        Bar string `json:"bar"`
    } `json:"foo"`
}

signals := &Signals{}
if err := datastar.ReadSignals(request, signals); err != nil {
    http.Error(w, err.Error(), http.StatusBadRequest)
    return
}
```

No example found for Java

```
@Serializable
data class Signals(
    val foo: String,
)

val jsonUnmarshaller: JsonUnmarshaller<Signals> = { json -> Json.decodeFromString(json) }

val request: Request =
    postRequest(
        body =
            """
            {
                "foo": "bar"
            }
            """.trimIndent(),
    )

val signals = readSignals(request, jsonUnmarshaller)
```

```
use starfederation\datastar\ServerSentEventGenerator;

// Reads all signals from the request.
$signals = ServerSentEventGenerator::readSignals();
```

```
from datastar_py.fastapi import datastar_response, read_signals

@app.get("/updates")
@datastar_response
async def updates(request: Request):
    # Retrieve a dictionary with the current state of the signals from the frontend
    signals = await read_signals(request)
```

```
# Setup with request
datastar = Datastar.new(request:, response:)

# Read signals
some_signal = datastar.signals[:some_signal]
```

No example found for Rust

No example found for TypeScript

## SSE Events

Datastar can stream zero or more Server-Sent Events (SSE) from the web server to the browser. There’s no special backend plumbing required to use SSE, just some special syntax. Fortunately, SSE is straightforward and provides us with some advantages, in addition to allowing us to send multiple events in a single response (in contrast to sending `text/html` or `application/json` responses).

First, set up your backend in the language of your choice. Familiarize yourself with sending SSE events, or use one of the backend SDKs to get up and running even faster. We’re going to use the SDKs in the examples below, which set the appropriate headers and format the events for us.

The following code would exist in a controller action endpoint in your backend.

```
;; Import the SDK's api and your adapter
(require
 '[starfederation.datastar.clojure.api :as d*]
 '[starfederation.datastar.clojure.adapter.http-kit :refer [->sse-response on-open]])

;; in a ring handler
(defn handler [request]
  ;; Create an SSE response
  (->sse-response request
                  {on-open
                   (fn [sse]
                     ;; Patches elements into the DOM
                     (d*/patch-elements! sse
                                         "<div id=\"question\">What do you put in a toaster?</div>")

                     ;; Patches signals
                     (d*/patch-signals! sse "{response: '', answer: 'bread'}"))}))
```

```
using StarFederation.Datastar.DependencyInjection;

// Adds Datastar as a service
builder.Services.AddDatastar();

app.MapGet("/", async (IDatastarService datastarService) =>
{
    // Patches elements into the DOM.
    await datastarService.PatchElementsAsync(@"<div id=""question"">What do you put in a toaster?</div>");

    // Patches signals.
    await datastarService.PatchSignalsAsync(new { response = "", answer = "bread" });
});
```

```
import ("github.com/starfederation/datastar-go/datastar")

// Creates a new `ServerSentEventGenerator` instance.
sse := datastar.NewSSE(w,r)

// Patches elements into the DOM.
sse.PatchElements(
    `<div id="question">What do you put in a toaster?</div>`
)

// Patches signals.
sse.PatchSignals([]byte(`{response: '', answer: 'bread'}`))
```

```
import starfederation.datastar.utils.ServerSentEventGenerator;

// Creates a new `ServerSentEventGenerator` instance.
AbstractResponseAdapter responseAdapter = new HttpServletResponseAdapter(response);
ServerSentEventGenerator generator = new ServerSentEventGenerator(responseAdapter);

// Patches elements into the DOM.
generator.send(PatchElements.builder()
    .data("<div id=\"question\">What do you put in a toaster?</div>")
    .build()
);

// Patches signals.
generator.send(PatchSignals.builder()
    .data("{\"response\": \"\", \"answer\": \"\"}")
    .build()
);
```

```
val generator = ServerSentEventGenerator(response)

generator.patchElements(
    elements = """<div id="question">What do you put in a toaster?</div>""",
)

generator.patchSignals(
    signals = """{"response": "", "answer": "bread"}""",
)
```

```
use starfederation\datastar\ServerSentEventGenerator;

// Creates a new `ServerSentEventGenerator` instance.
$sse = new ServerSentEventGenerator();

// Patches elements into the DOM.
$sse->patchElements(
    '<div id="question">What do you put in a toaster?</div>'
);

// Patches signals.
$sse->patchSignals(['response' => '', 'answer' => 'bread']);
```

```
from datastar_py import ServerSentEventGenerator as SSE
from datastar_py.litestar import DatastarResponse

async def endpoint():
    return DatastarResponse([
        SSE.patch_elements('<div id="question">What do you put in a toaster?</div>'),
        SSE.patch_signals({"response": "", "answer": "bread"})
    ])
```

```
require 'datastar'

# Create a Datastar::Dispatcher instance

datastar = Datastar.new(request:, response:)

# In a Rack handler, you can instantiate from the Rack env
# datastar = Datastar.from_rack_env(env)

# Start a streaming response
datastar.stream do |sse|
  # Patches elements into the DOM
  sse.patch_elements %(<div id="question">What do you put in a toaster?</div>)

  # Patches signals
  sse.patch_signals(response: '', answer: 'bread')
end
```

```
use datastar::prelude::*;
use async_stream::stream;

Sse(stream! {
    // Patches elements into the DOM.
    yield PatchElements::new("<div id='question'>What do you put in a toaster?</div>").into();

    // Patches signals.
    yield PatchSignals::new("{response: '', answer: 'bread'}").into();
})
```

```
// Creates a new `ServerSentEventGenerator` instance (this also sends required headers)
ServerSentEventGenerator.stream(req, res, (stream) => {
      // Patches elements into the DOM.
     stream.patchElements(`<div id="question">What do you put in a toaster?</div>`);

     // Patches signals.
     stream.patchSignals({'response':  '', 'answer': 'bread'});
});
```

The `PatchElements()` function updates the provided HTML element into the DOM, replacing the element with `id="question"`. An element with the ID `question` must *already* exist in the DOM.

The `PatchSignals()` function updates the `response` and `answer` signals into the frontend signals.

With our backend in place, we can now use the `data-on:click` attribute to trigger the `@get()` action, which sends a `GET` request to the `/actions/quiz` endpoint on the server when a button is clicked.

```
<div
    data-signals="{response: '', answer: ''}"
    data-computed:correct="$response.toLowerCase() == $answer"
>
    <div id="question"></div>
    <button data-on:click="@get('/actions/quiz')">Fetch a question</button>
    <button
        data-show="$answer != ''"
        data-on:click="$response = prompt('Answer:') ?? ''"
    >
        BUZZ
    </button>
    <div data-show="$response != ''">
        You answered “<span data-text="$response"></span>”.
        <span data-show="$correct">That is correct ✅</span>
        <span data-show="!$correct">
        The correct answer is “<span data-text="$answer"></span>” 🤷
        </span>
    </div>
</div>
```

Now when the `Fetch a question` button is clicked, the server will respond with an event to modify the `question` element in the DOM and an event to modify the `response` and `answer` signals. We’re driving state from the backend!

Demo

...

Fetch a question BUZZ

You answered “”. That is correct ✅ The correct answer is “” 🤷

### `data-indicator`

The `data-indicator` attribute sets the value of a signal to `true` while the request is in flight, otherwise `false`. We can use this signal to show a loading indicator, which may be desirable for slower responses.

```
<div id="question"></div>
<button
    data-on:click="@get('/actions/quiz')"
    data-indicator:fetching
>
    Fetch a question
</button>
<div data-class:loading="$fetching" class="indicator"></div>
```

Demo

...

Fetch a question

![Indicator](https://data-star.dev/cdn-cgi/image/format=auto,width=32/static/images/rocket-animated-1d781383a0d7cbb1eb575806abeec107c8a915806fb55ee19e4e33e8632c75e5.gif)

## Backend Actions

We’re not limited to sending just `GET` requests. Datastar provides backend actions for each of the methods available: `@get()`, `@post()`, `@put()`, `@patch()` and `@delete()`.

Here’s how we can send an answer to the server for processing, using a `POST` request.

```
<button data-on:click="@post('/actions/quiz')">
    Submit answer
</button>
```

One of the benefits of using SSE is that we can send multiple events (patch elements and patch signals) in a single response.

```
(d*/patch-elements! sse "<div id=\"question\">...</div>")
(d*/patch-elements! sse "<div id=\"instructions\">...</div>")
(d*/patch-signals! sse "{answer: '...', prize: '...'}")
```

```
datastarService.PatchElementsAsync(@"<div id=""question"">...</div>");
datastarService.PatchElementsAsync(@"<div id=""instructions"">...</div>");
datastarService.PatchSignalsAsync(new { answer = "...", prize = "..." } );
```

```
sse.PatchElements(`<div id="question">...</div>`)
sse.PatchElements(`<div id="instructions">...</div>`)
sse.PatchSignals([]byte(`{answer: '...', prize: '...'}`))
```

```
generator.send(PatchElements.builder()
    .data("<div id=\"question\">...</div>")
    .build()
);
generator.send(PatchElements.builder()
    .data("<div id=\"instructions\">...</div>")
    .build()
);
generator.send(PatchSignals.builder()
    .data("{\"answer\": \"...\", \"prize\": \"...\"}")
    .build()
);
```

```
generator.patchElements(
    elements = """<div id="question">...</div>""",
)
generator.patchElements(
    elements = """<div id="instructions">...</div>""",
)
generator.patchSignals(
    signals = """{"answer": "...", "prize": "..."}""",
)
```

```
$sse->patchElements('<div id="question">...</div>');
$sse->patchElements('<div id="instructions">...</div>');
$sse->patchSignals(['answer' => '...', 'prize' => '...']);
```

```
return DatastarResponse([
    SSE.patch_elements('<div id="question">...</div>'),
    SSE.patch_elements('<div id="instructions">...</div>'),
    SSE.patch_signals({"answer": "...", "prize": "..."})
])
```

```
datastar.stream do |sse|
  sse.patch_elements('<div id="question">...</div>')
  sse.patch_elements('<div id="instructions">...</div>')
  sse.patch_signals(answer: '...', prize: '...')
end
```

```
yield PatchElements::new("<div id='question'>...</div>").into()
yield PatchElements::new("<div id='instructions'>...</div>").into()
yield PatchSignals::new("{answer: '...', prize: '...'}").into()
```

```
stream.patchElements('<div id="question">...</div>');
stream.patchElements('<div id="instructions">...</div>');
stream.patchSignals({'answer': '...', 'prize': '...'});
```

> In addition to your browser’s dev tools, the Datastar Inspector can be used to monitor and inspect SSE events received by Datastar.

Read more about SSE events in the reference.

## Congratulations

You’ve actually read the entire guide! You should now know how to use Datastar to build reactive applications that communicate with the backend using backend requests and SSE events.

Feel free to dive into the reference and explore the examples next, to learn more about what you can do with Datastar.

# Reference

# Attributes

Data attributes are evaluated in the order they appear in the DOM, have special casing rules, can be aliased to avoid conflicts with other libraries, can contain Datastar expressions, and have runtime error handling.

> The Datastar VSCode extension and IntelliJ plugin provide autocompletion for all available `data-*` attributes.

### `data-attr`

Sets the value of any HTML attribute to an expression, and keeps it in sync.

```
<div data-attr:title="$foo"></div>
```

The `data-attr` attribute can also be used to set the values of multiple attributes on an element using a set of key-value pairs, where the keys represent attribute names and the values represent expressions.

```
<div data-attr="{title: $foo, disabled: $bar}"></div>
```

### `data-bind`

Creates a signal (if one doesn’t already exist) and sets up two-way data binding between it and an element’s value. This means that the value of the element is updated when the signal changes, and the signal value is updated when the value of the element changes.

The `data-bind` attribute can be placed on any HTML element on which data can be input or choices selected (`input`, `select`,`textarea` elements, and web components). Event listeners are added for `change` and `input` events.

```
<input data-bind:foo />
```

The signal name can be specified in the key (as above), or in the value (as below). This can be useful depending on the templating language you are using.

```
<input data-bind="foo" />
```

The initial value of the signal is set to the value of the element, unless a signal has already been defined. So in the example below, `$foo` is set to `bar`.

```
<input data-bind:foo value="bar" />
```

Whereas in the example below, `$foo` inherits the value `baz` of the predefined signal.

```
<div data-signals:foo="baz">
    <input data-bind:foo value="bar" />
</div>
```

#### Predefined Signal Types

When you predefine a signal, its **type** is preserved during binding. Whenever the element’s value changes, the signal value is automatically converted to match the original type.

For example, in the code below, `$foo` is set to the **number** `10` (not the string `"10"`) when the option is selected.

```
<div data-signals:foo="0">
    <select data-bind:foo>
        <option value="10">10</option>
    </select>
</div>
```

In the same way, you can assign multiple input values to a single signal by predefining it as an **array**. In the example below, `$foo` becomes `["bar", "baz"]` when both checkboxes are checked, and `["", ""]` when neither is checked.

```
<div data-signals:foo="[]">
    <input data-bind:foo type="checkbox" value="bar" />
    <input data-bind:foo type="checkbox" value="baz" />
</div>
```

#### File Uploads

Input fields of type `file` will automatically encode file contents in base64. This means that a form is not required.

```
<input type="file" data-bind:files multiple />
```

The resulting signal is in the format `{ name: string, contents: string, mime: string }[]`. See the file upload example.

> If you want files to be uploaded to the server, rather than be converted to signals, use a form and with `multipart/form-data` in the `enctype` attribute. See the backend actions reference.

#### Modifiers

Modifiers allow you to modify behavior when binding signals using a key.

- `__case` – Converts the casing of the signal name.
  
  - `.camel` – Camel case: `mySignal` (default)
  - `.kebab` – Kebab case: `my-signal`
  - `.snake` – Snake case: `my_signal`
  - `.pascal` – Pascal case: `MySignal`

```
<input data-bind:my-signal__case.kebab />
```

### `data-class`

Adds or removes a class to or from an element based on an expression.

```
<div data-class:hidden="$foo"></div>
```

If the expression evaluates to `true`, the `hidden` class is added to the element; otherwise, it is removed.

The `data-class` attribute can also be used to add or remove multiple classes from an element using a set of key-value pairs, where the keys represent class names and the values represent expressions.

```
<div data-class="{hidden: $foo, 'font-bold': $bar}"></div>
```

#### Modifiers

Modifiers allow you to modify behavior when defining a class name using a key.

- `__case` – Converts the casing of the class.
  
  - `.camel` – Camel case: `myClass`
  - `.kebab` – Kebab case: `my-class` (default)
  - `.snake` – Snake case: `my_class`
  - `.pascal` – Pascal case: `MyClass`

```
<div data-class:my-class__case.camel="$foo"></div>
```

### `data-computed`

Creates a signal that is computed based on an expression. The computed signal is read-only, and its value is automatically updated when any signals in the expression are updated.

```
<div data-computed:foo="$bar + $baz"></div>
```

Computed signals are useful for memoizing expressions containing other signals. Their values can be used in other expressions.

```
<div data-computed:foo="$bar + $baz"></div>
<div data-text="$foo"></div>
```

> Computed signal expressions must not be used for performing actions (changing other signals, actions, JavaScript functions, etc.). If you need to perform an action in response to a signal change, use the `data-effect` attribute.

The `data-computed` attribute can also be used to create computed signal using a set of key-value pairs, where the keys represent signal names and the values are callables (usually arrow functions) that return a reactive value.

```
<div data-computed="{foo: () => $bar + $baz}"></div>
```

#### Modifiers

Modifiers allow you to modify behavior when defining computed signals using a key.

- `__case` – Converts the casing of the signal name.
  
  - `.camel` – Camel case: `mySignal` (default)
  - `.kebab` – Kebab case: `my-signal`
  - `.snake` – Snake case: `my_signal`
  - `.pascal` – Pascal case: `MySignal`

```
<div data-computed:my-signal__case.kebab="$bar + $baz"></div>
```

### `data-effect`

Executes an expression on page load and whenever any signals in the expression change. This is useful for performing side effects, such as updating other signals, making requests to the backend, or manipulating the DOM.

```
<div data-effect="$foo = $bar + $baz"></div>
```

### `data-ignore`

Datastar walks the entire DOM and applies plugins to each element it encounters. It’s possible to tell Datastar to ignore an element and its descendants by placing a `data-ignore` attribute on it. This can be useful for preventing naming conflicts with third-party libraries, or when you are unable to escape user input.

```
<div data-ignore data-show-thirdpartylib="">
    <div>
        Datastar will not process this element.
    </div>
</div>
```

#### Modifiers

- `__self` – Only ignore the element itself, not its descendants.

### `data-ignore-morph`

Similar to the `data-ignore` attribute, the `data-ignore-morph` attribute tells the `PatchElements` watcher to skip processing an element and its children when morphing elements.

```
<div data-ignore-morph>
    This element will not be morphed.
</div>
```

> To remove the `data-ignore-morph` attribute from an element, simply patch the element with the `data-ignore-morph` attribute removed.

### `data-indicator`

Creates a signal and sets its value to `true` while a fetch request is in flight, otherwise `false`. The signal can be used to show a loading indicator.

```
<button data-on:click="@get('/endpoint')"
        data-indicator:fetching
></button>
```

This can be useful for showing a loading spinner, disabling a button, etc.

```
<button data-on:click="@get('/endpoint')"
        data-indicator:fetching
        data-attr:disabled="$fetching"
></button>
<div data-show="$fetching">Loading...</div>
```

The signal name can be specified in the key (as above), or in the value (as below). This can be useful depending on the templating language you are using.

```
<button data-indicator="fetching"></button>
```

When using `data-indicator` with a fetch request initiated in a `data-init` attribute, you should ensure that the indicator signal is created before the fetch request is initialized.

```
<div data-indicator:fetching data-init="@get('/endpoint')"></div>
```

#### Modifiers

Modifiers allow you to modify behavior when defining indicator signals using a key.

- `__case` – Converts the casing of the signal name.
  
  - `.camel` – Camel case: `mySignal` (default)
  - `.kebab` – Kebab case: `my-signal`
  - `.snake` – Snake case: `my_signal`
  - `.pascal` – Pascal case: `MySignal`

### `data-init`

Runs an expression when the attribute is initialized. This can happen on page load, when an element is patched into the DOM, and any time the attribute is modified (via a backend action or otherwise).

> The expression contained in the `data-init` attribute is executed when the element attribute is loaded into the DOM. This can happen on page load, when an element is patched into the DOM, and any time the attribute is modified (via a backend action or otherwise).

```
<div data-init="$count = 1"></div>
```

#### Modifiers

Modifiers allow you to add a delay to the event listener.

- `__delay` – Delay the event listener.
  
  - `.500ms` – Delay for 500 milliseconds (accepts any integer).
  - `.1s` – Delay for 1 second (accepts any integer).
- `__viewtransition` – Wraps the expression in `document.startViewTransition()` when the View Transition API is available.

```
<div data-init__delay.500ms="$count = 1"></div>
```

### `data-json-signals`

Sets the text content of an element to a reactive JSON stringified version of signals. Useful when troubleshooting an issue.

```
<!-- Display all signals -->
<pre data-json-signals></pre>
```

You can optionally provide a filter object to include or exclude specific signals using regular expressions.

```
<!-- Only show signals that include "user" in their path -->
<pre data-json-signals="{include: /user/}"></pre>

<!-- Show all signals except those ending with "temp" -->
<pre data-json-signals="{exclude: /temp$/}"></pre>

<!-- Combine include and exclude filters -->
<pre data-json-signals="{include: /^app/, exclude: /password/}"></pre>
```

#### Modifiers

Modifiers allow you to modify the output format.

- `__terse` – Outputs a more compact JSON format without extra whitespace. Useful for displaying filtered data inline.

```
<!-- Display filtered signals in a compact format -->
<pre data-json-signals__terse="{include: /counter/}"></pre>
```

### `data-on`

Attaches an event listener to an element, executing an expression whenever the event is triggered.

```
<button data-on:click="$foo = ''">Reset</button>
```

An `evt` variable that represents the event object is available in the expression.

```
<div data-on:myevent="$foo = evt.detail"></div>
```

The `data-on` attribute works with events and custom events. The `data-on:submit` event listener prevents the default submission behavior of forms.

#### Modifiers

Modifiers allow you to modify behavior when events are triggered. Some modifiers have tags to further modify the behavior.

- `__once` * – Only trigger the event listener once.
- `__passive` * – Do not call `preventDefault` on the event listener.
- `__capture` * – Use a capture event listener.
- `__case` – Converts the casing of the event.
  
  - `.camel` – Camel case: `myEvent`
  - `.kebab` – Kebab case: `my-event` (default)
  - `.snake` – Snake case: `my_event`
  - `.pascal` – Pascal case: `MyEvent`
- `__delay` – Delay the event listener.
  
  - `.500ms` – Delay for 500 milliseconds (accepts any integer).
  - `.1s` – Delay for 1 second (accepts any integer).
- `__debounce` – Debounce the event listener.
  
  - `.500ms` – Debounce for 500 milliseconds (accepts any integer).
  - `.1s` – Debounce for 1 second (accepts any integer).
  - `.leading` – Debounce with leading edge (must come after timing).
  - `.notrailing` – Debounce without trailing edge (must come after timing).
- `__throttle` – Throttle the event listener.
  
  - `.500ms` – Throttle for 500 milliseconds (accepts any integer).
  - `.1s` – Throttle for 1 second (accepts any integer).
  - `.noleading` – Throttle without leading edge (must come after timing).
  - `.trailing` – Throttle with trailing edge (must come after timing).
- `__viewtransition` – Wraps the expression in `document.startViewTransition()` when the View Transition API is available.
- `__window` – Attaches the event listener to the `window` element.
- `__outside` – Triggers when the event is outside the element.
- `__prevent` – Calls `preventDefault` on the event listener.
- `__stop` – Calls `stopPropagation` on the event listener.

** Only works with built-in events.*

```
<button data-on:click__window__debounce.500ms.leading="$foo = ''"></button>
<div data-on:my-event__case.camel="$foo = ''"></div>
```

### `data-on-intersect`

Runs an expression when the element intersects with the viewport.

```
<div data-on-intersect="$intersected = true"></div>
```

#### Modifiers

Modifiers allow you to modify the element intersection behavior and the timing of the event listener.

- `__once` – Only triggers the event once.
- `__half` – Triggers when half of the element is visible.
- `__full` – Triggers when the full element is visible.
- `__delay` – Delay the event listener.
  
  - `.500ms` – Delay for 500 milliseconds (accepts any integer).
  - `.1s` – Delay for 1 second (accepts any integer).
- `__debounce` – Debounce the event listener.
  
  - `.500ms` – Debounce for 500 milliseconds (accepts any integer).
  - `.1s` – Debounce for 1 second (accepts any integer).
  - `.leading` – Debounce with leading edge (must come after timing).
  - `.notrailing` – Debounce without trailing edge (must come after timing).
- `__throttle` – Throttle the event listener.
  
  - `.500ms` – Throttle for 500 milliseconds (accepts any integer).
  - `.1s` – Throttle for 1 second (accepts any integer).
  - `.noleading` – Throttle without leading edge (must come after timing).
  - `.trailing` – Throttle with trailing edge (must come after timing).
- `__viewtransition` – Wraps the expression in `document.startViewTransition()` when the View Transition API is available.

```
<div data-on-intersect__once__full="$fullyIntersected = true"></div>
```

### `data-on-interval`

Runs an expression at a regular interval. The interval duration defaults to one second and can be modified using the `__duration` modifier.

```
<div data-on-interval="$count++"></div>
```

#### Modifiers

Modifiers allow you to modify the interval duration.

- `__duration` – Sets the interval duration.
  
  - `.500ms` – Interval duration of 500 milliseconds (accepts any integer).
  - `.1s` – Interval duration of 1 second (default).
  - `.leading` – Execute the first interval immediately.
- `__viewtransition` – Wraps the expression in `document.startViewTransition()` when the View Transition API is available.

```
<div data-on-interval__duration.500ms="$count++"></div>
```

### `data-on-signal-patch`

Runs an expression whenever any signals are patched. This is useful for tracking changes, updating computed values, or triggering side effects when data updates.

```
<div data-on-signal-patch="console.log('A signal changed!')"></div>
```

The `patch` variable is available in the expression and contains the signal patch details.

```
<div data-on-signal-patch="console.log('Signal patch:', patch)"></div>
```

You can filter which signals to watch using the `data-on-signal-patch-filter` attribute.

#### Modifiers

Modifiers allow you to modify the timing of the event listener.

- `__delay` – Delay the event listener.
  
  - `.500ms` – Delay for 500 milliseconds (accepts any integer).
  - `.1s` – Delay for 1 second (accepts any integer).
- `__debounce` – Debounce the event listener.
  
  - `.500ms` – Debounce for 500 milliseconds (accepts any integer).
  - `.1s` – Debounce for 1 second (accepts any integer).
  - `.leading` – Debounce with leading edge (must come after timing).
  - `.notrailing` – Debounce without trailing edge (must come after timing).
- `__throttle` – Throttle the event listener.
  
  - `.500ms` – Throttle for 500 milliseconds (accepts any integer).
  - `.1s` – Throttle for 1 second (accepts any integer).
  - `.noleading` – Throttle without leading edge (must come after timing).
  - `.trailing` – Throttle with trailing edge (must come after timing).

```
<div data-on-signal-patch__debounce.500ms="doSomething()"></div>
```

### `data-on-signal-patch-filter`

Filters which signals to watch when using the `data-on-signal-patch` attribute.

The `data-on-signal-patch-filter` attribute accepts an object with `include` and/or `exclude` properties that are regular expressions.

```
<!-- Only react to counter signal changes -->
<div data-on-signal-patch-filter="{include: /^counter$/}"></div>

<!-- React to all changes except those ending with "changes" -->
<div data-on-signal-patch-filter="{exclude: /changes$/}"></div>

<!-- Combine include and exclude filters -->
<div data-on-signal-patch-filter="{include: /user/, exclude: /password/}"></div>
```

### `data-preserve-attr`

Preserves the value of an attribute when morphing DOM elements.

```
<details open data-preserve-attr="open">
    <summary>Title</summary>
    Content
</details>
```

You can preserve multiple attributes by separating them with a space.

```
<details open class="foo" data-preserve-attr="open class">
    <summary>Title</summary>
    Content
</details>
```

### `data-ref`

Creates a new signal that is a reference to the element on which the data attribute is placed.

```
<div data-ref:foo></div>
```

The signal name can be specified in the key (as above), or in the value (as below). This can be useful depending on the templating language you are using.

```
<div data-ref="foo"></div>
```

The signal value can then be used to reference the element.

```
$foo is a reference to a <span data-text="$foo.tagName"></span> element
```

#### Modifiers

Modifiers allow you to modify behavior when defining references using a key.

- `__case` – Converts the casing of the signal name.
  
  - `.camel` – Camel case: `mySignal` (default)
  - `.kebab` – Kebab case: `my-signal`
  - `.snake` – Snake case: `my_signal`
  - `.pascal` – Pascal case: `MySignal`

```
<div data-ref:my-signal__case.kebab></div>
```

### `data-show`

Shows or hides an element based on whether an expression evaluates to `true` or `false`. For anything with custom requirements, use `data-class` instead.

```
<div data-show="$foo"></div>
```

To prevent flickering of the element before Datastar has processed the DOM, you can add a `display: none` style to the element to hide it initially.

```
<div data-show="$foo" style="display: none"></div>
```

### `data-signals`

Patches (adds, updates or removes) one or more signals into the existing signals. Values defined later in the DOM tree override those defined earlier.

```
<div data-signals:foo="1"></div>
```

Signals can be nested using dot-notation.

```
<div data-signals:foo.bar="1"></div>
```

The `data-signals` attribute can also be used to patch multiple signals using a set of key-value pairs, where the keys represent signal names and the values represent expressions.

```
<div data-signals="{foo: {bar: 1, baz: 2}}"></div>
```

The value above is written in JavaScript object notation, but JSON, which is a subset and which most templating languages have built-in support for, is also allowed.

Setting a signal’s value to `null` or `undefined` removes the signal.

```
<div data-signals="{foo: null}"></div>
```

Keys used in `data-signals:*` are converted to camel case, so the signal name `mySignal` must be written as `data-signals:my-signal` or `data-signals="{mySignal: 1}"`.

Signals beginning with an underscore are *not* included in requests to the backend by default. You can opt to include them by modifying the value of the `filterSignals` option.

> Signal names cannot begin with nor contain a double underscore (`__`), due to its use as a modifier delimiter.

#### Modifiers

Modifiers allow you to modify behavior when patching signals using a key.

- `__case` – Converts the casing of the signal name.
  
  - `.camel` – Camel case: `mySignal` (default)
  - `.kebab` – Kebab case: `my-signal`
  - `.snake` – Snake case: `my_signal`
  - `.pascal` – Pascal case: `MySignal`
- `__ifmissing` Only patches signals if their keys do not already exist. This is useful for setting defaults without overwriting existing values.

```
<div data-signals:my-signal__case.kebab="1"
     data-signals:foo__ifmissing="1"
></div>
```

### `data-style`

Sets the value of inline CSS styles on an element based on an expression, and keeps them in sync.

```
<div data-style:background-color="$usingRed ? 'red' : 'blue'"></div>
<div data-style:display="$hiding && 'none'"></div>
```

The `data-style` attribute can also be used to set multiple style properties on an element using a set of key-value pairs, where the keys represent CSS property names and the values represent expressions.

```
<div data-style="{
    display: $hiding ? 'none' : 'flex',
    flexDirection: 'column',
    color: $usingRed ? 'red' : 'green'
}"></div>
```

Style properties can be specified in either camelCase (e.g., `backgroundColor`) or kebab-case (e.g., `background-color`). They will be automatically converted to the appropriate format.

Empty string, `null`, `undefined`, or `false` values will restore the original inline style value if one existed, or remove the style property if there was no initial value. This allows you to use the logical AND operator (`&&`) for conditional styles: `$condition && 'value'` will apply the style when the condition is true and restore the original value when false.

```
<!-- When $x is false, color remains red from inline style -->
<div style="color: red;" data-style:color="$x && 'green'"></div>

<!-- When $hiding is true, display becomes none; when false, reverts to flex from inline style -->
<div style="display: flex;" data-style:display="$hiding && 'none'"></div>
```

The plugin tracks initial inline style values and restores them when data-style expressions become falsy or during cleanup. This ensures existing inline styles are preserved and only the dynamic changes are managed by Datastar.

### `data-text`

Binds the text content of an element to an expression.

```
<div data-text="$foo"></div>
```

## Pro Attributes

The Pro attributes add functionality to the free open source Datastar framework. These attributes are available under a commercial license that helps fund our open source work.

### `data-animate` Pro

Allows you to animate element attributes over time. Animated attributes are updated reactively whenever signals used in the expression change.

### `data-custom-validity` Pro

Allows you to add custom validity to an element using an expression. The expression must evaluate to a string that will be set as the custom validity message. If the string is empty, the input is considered valid. If the string is non-empty, the input is considered invalid and the string is used as the reported message.

```
<form>
    <input data-bind:foo name="foo" />
    <input data-bind:bar name="bar"
           data-custom-validity="$foo === $bar ? '' : 'Values must be the same.'"
    />
    <button>Submit form</button>
</form>
```

### `data-on-raf` Pro

Runs an expression on every `requestAnimationFrame` event.

```
<div data-on-raf="$count++"></div>
```

#### Modifiers

Modifiers allow you to modify the timing of the event listener.

- `__throttle` – Throttle the event listener.
  
  - `.500ms` – Throttle for 500 milliseconds (accepts any integer).
  - `.1s` – Throttle for 1 second (accepts any integer).
  - `.noleading` – Throttle without leading edge (must come after timing).
  - `.trailing` – Throttle with trailing edge (must come after timing).

```
<div data-on-raf__throttle.10ms="$count++"></div>
```

### `data-on-resize` Pro

Runs an expression whenever an element’s dimensions change.

```
<div data-on-resize="$count++"></div>
```

#### Modifiers

Modifiers allow you to modify the timing of the event listener.

- `__debounce` – Debounce the event listener.
  
  - `.500ms` – Debounce for 500 milliseconds (accepts any integer).
  - `.1s` – Debounce for 1 second (accepts any integer).
  - `.leading` – Debounce with leading edge (must come after timing).
  - `.notrailing` – Debounce without trailing edge (must come after timing).
- `__throttle` – Throttle the event listener.
  
  - `.500ms` – Throttle for 500 milliseconds (accepts any integer).
  - `.1s` – Throttle for 1 second (accepts any integer).
  - `.noleading` – Throttle without leading edge (must come after timing).
  - `.trailing` – Throttle with trailing edge (must come after timing).

```
<div data-on-resize__debounce.10ms="$count++"></div>
```

### `data-persist` Pro

Persists signals in local storage. This is useful for storing values between page loads.

```
<div data-persist></div>
```

The signals to be persisted can be filtered by providing a value that is an object with `include` and/or `exclude` properties that are regular expressions.

```
<div data-persist="{include: /foo/, exclude: /bar/}"></div>
```

You can use a custom storage key by adding it after `data-persist:`. By default, signals are stored using the key `datastar`.

```
<div data-persist:mykey></div>
```

#### Modifiers

Modifiers allow you to modify the storage target.

- `__session` – Persists signals in session storage instead of local storage.

```
<!-- Persists signals using a custom key `mykey` in session storage -->
<div data-persist:mykey__session></div>
```

### `data-query-string` Pro

Syncs query string params to signal values on page load, and syncs signal values to query string params on change.

```
<div data-query-string></div>
```

The signals to be synced can be filtered by providing a value that is an object with `include` and/or `exclude` properties that are regular expressions.

```
<div data-query-string="{include: /foo/, exclude: /bar/}"></div>
```

#### Modifiers

Modifiers allow you to enable history support.

- `__filter` – Filters out empty values when syncing signal values to query string params.
- `__history` – Enables history support – each time a matching signal changes, a new entry is added to the browser’s history stack. Signal values are restored from the query string params on popstate events.

```
<div data-query-string__filter__history></div>
```

### `data-replace-url` Pro

Replaces the URL in the browser without reloading the page. The value can be a relative or absolute URL, and is an evaluated expression.

```
<div data-replace-url="`/page${page}`"></div>
```

### `data-scroll-into-view` Pro

Scrolls the element into view. Useful when updating the DOM from the backend, and you want to scroll to the new content.

```
<div data-scroll-into-view></div>
```

#### Modifiers

Modifiers allow you to modify scrolling behavior.

- `__smooth` – Scrolling is animated smoothly.
- `__instant` – Scrolling is instant.
- `__auto` – Scrolling is determined by the computed `scroll-behavior` CSS property.
- `__hstart` – Scrolls to the left of the element.
- `__hcenter` – Scrolls to the horizontal center of the element.
- `__hend` – Scrolls to the right of the element.
- `__hnearest` – Scrolls to the nearest horizontal edge of the element.
- `__vstart` – Scrolls to the top of the element.
- `__vcenter` – Scrolls to the vertical center of the element.
- `__vend` – Scrolls to the bottom of the element.
- `__vnearest` – Scrolls to the nearest vertical edge of the element.
- `__focus` – Focuses the element after scrolling.

### `data-rocket` Pro

Creates a Rocket web component. See the Rocket reference for details.

### `data-view-transition` Pro

Sets the `view-transition-name` style attribute explicitly.

```
<div data-view-transition="$foo"></div>
```

Page level transitions are automatically handled by an injected meta tag. Inter-page elements are automatically transitioned if the View Transition API is available in the browser and `useViewTransitions` is `true`.

## Attribute Order

Elements are evaluated by walking the DOM in a depth-first manner, and attributes are processed in the order they appear in the element. This is important in some cases, such as when using `data-indicator` with a fetch request initiated in a `data-init` attribute, in which the indicator signal must be created before the fetch request is initialized.

```
<div data-indicator:fetching data-init="@get('/endpoint')"></div>
```

## Attribute Casing

According to the HTML specification, all `data-*` attributes (not Datastar the framework, but any time a data attribute appears in the DOM) are case in-sensitive, but are converted to `camelCase` when accessed from JavaScript by Datastar.

Datastar handles casing of data attributes in two ways:

1. The keys used in attributes that define signals (`data-signals:*`, `data-computed:*`, etc.), are converted to `camelCase`. For example, `data-signals:my-signal` defines a signal named `mySignal`. You would use the signal in a Datastar expression as `$mySignal`.
2. The keys used by all other attributes are, by default, converted to `kebab-case`. For example, `data-class:text-blue-700` adds or removes the class `text-blue-700`, and `data-on:rocket-launched` would react to the event named `rocket-launched`.

You can use the `__case` modifier to convert between `camelCase`, `kebab-case`, `snake_case`, and `PascalCase`, or alternatively use object syntax when available.

For example, if listening for an event called `widgetLoaded`, you would use `data-on:widget-loaded__case.camel`.

## Aliasing Attributes

It is possible to alias `data-*` attributes to a custom alias (`data-foo-*`, for example) using the bundler. A custom alias should *only* be used if you have a conflict with a legacy library and `data-ignore` cannot be used.

We maintain a `data-star-*` aliased version that can be included as follows.

```
<script type="module" src="https://cdn.jsdelivr.net/gh/starfederation/[email protected]/bundles/datastar-aliased.js"></script>
```

## Datastar Expressions

Datastar expressions used in `data-*` attributes can parse signals (prefixed with `$`).

A variable `el` is available in every Datastar expression, representing the element that the attribute exists on.

```
<div id="bar" data-text="$foo + el.id"></div>
```

Read more about Datastar expressions in the guide.

## Error Handling

Datastar has built-in error handling and reporting for runtime errors. When a data attribute is used incorrectly, for example `data-text-foo`, the following error message is logged to the browser console.

```
Uncaught datastar runtime error: textKeyNotAllowed
More info: https://data-star.dev/errors/key_not_allowed?metadata=%7B%22plugin%22%3A%7B%22name%22%3A%22text%22%2C%22type%22%3A%22attribute%22%7D%2C%22element%22%3A%7B%22id%22%3A%22%22%2C%22tag%22%3A%22DIV%22%7D%2C%22expression%22%3A%7B%22rawKey%22%3A%22textFoo%22%2C%22key%22%3A%22foo%22%2C%22value%22%3A%22%22%2C%22fnContent%22%3A%22%22%7D%7D
Context: {
    "plugin": {
        "name": "text",
        "type": "attribute"
    },
    "element": {
        "id": "",
        "tag": "DIV"
    },
    "expression": {
        "rawKey": "textFoo",
        "key": "foo",
        "value": "",
        "fnContent": ""
    }
}
```

The “More info” link takes you directly to a context-aware error page that explains error and provides correct sample usage. See the error page for the example above, and all available error messages in the sidebar menu.

# Actions

Datastar provides actions (helper functions) that can be used in Datastar expressions.

> The `@` prefix designates actions that are safe to use in expressions. This is a security feature that prevents arbitrary JavaScript from being executed in the browser. Datastar uses `Function()` constructors to create and execute these actions in a secure and controlled sandboxed environment.

### `@peek()`

> `@peek(callable: () => any)`

Allows accessing signals without subscribing to their changes in expressions.

```
<div data-text="$foo + @peek(() => $bar)"></div>
```

In the example above, the expression in the `data-text` attribute will be re-evaluated whenever `$foo` changes, but it will *not* be re-evaluated when `$bar` changes, since it is evaluated inside the `@peek()` action.

### `@setAll()`

> `@setAll(value: any, filter?: {include: RegExp, exclude?: RegExp})`

Sets the value of all matching signals (or all signals if no filter is used) to the expression provided in the first argument. The second argument is an optional filter object with an `include` property that accepts a regular expression to match signal paths. You can optionally provide an `exclude` property to exclude specific patterns.

> The Datastar Inspector can be used to inspect and filter current signals and view signal patch events in real-time.

```
<!-- Sets the `foo` signal only -->
<div data-signals:foo="false">
    <button data-on:click="@setAll(true, {include: /^foo$/})"></button>
</div>

<!-- Sets all signals starting with `user.` -->
<div data-signals="{user: {name: '', nickname: ''}}">
    <button data-on:click="@setAll('johnny', {include: /^user\./})"></button>
</div>

<!-- Sets all signals except those ending with `_temp` -->
<div data-signals="{data: '', data_temp: '', info: '', info_temp: ''}">
    <button data-on:click="@setAll('reset', {include: /.*/, exclude: /_temp$/})"></button>
</div>
```

### `@toggleAll()`

> `@toggleAll(filter?: {include: RegExp, exclude?: RegExp})`

Toggles the boolean value of all matching signals (or all signals if no filter is used). The argument is an optional filter object with an `include` property that accepts a regular expression to match signal paths. You can optionally provide an `exclude` property to exclude specific patterns.

> The Datastar Inspector can be used to inspect and filter current signals and view signal patch events in real-time.

```
<!-- Toggles the `foo` signal only -->
<div data-signals:foo="false">
    <button data-on:click="@toggleAll({include: /^foo$/})"></button>
</div>

<!-- Toggles all signals starting with `is` -->
<div data-signals="{isOpen: false, isActive: true, isEnabled: false}">
    <button data-on:click="@toggleAll({include: /^is/})"></button>
</div>

<!-- Toggles signals starting with `settings.` -->
<div data-signals="{settings: {darkMode: false, autoSave: true}}">
    <button data-on:click="@toggleAll({include: /^settings\./})"></button>
</div>
```

## Backend Actions

### `@get()`

> `@get(uri: string, options={ })`

Sends a `GET` request to the backend using the Fetch API. The URI can be any valid endpoint and the response must contain zero or more Datastar SSE events.

```
<button data-on:click="@get('/endpoint')"></button>
```

By default, requests are sent with a `Datastar-Request: true` header, and a `{datastar: *}` object containing all existing signals, except those beginning with an underscore. This behavior can be changed using the `filterSignals` option, which allows you to include or exclude specific signals using regular expressions.

> When using a `get` request, the signals are sent as a query parameter, otherwise they are sent as a JSON body.

When a page is hidden (in a background tab, for example), the default behavior is for the SSE connection to be closed, and reopened when the page becomes visible again. To keep the connection open when the page is hidden, set the `openWhenHidden` option to `true`.

```
<button data-on:click="@get('/endpoint', {openWhenHidden: true})"></button>
```

It’s possible to send form encoded requests by setting the `contentType` option to `form`. This sends requests using `application/x-www-form-urlencoded` encoding.

```
<button data-on:click="@get('/endpoint', {contentType: 'form'})"></button>
```

It’s also possible to send requests using `multipart/form-data` encoding by specifying it in the `form` element’s `enctype` attribute. This should be used when uploading files. See the form data example.

```
<form enctype="multipart/form-data">
    <input type="file" name="file" />
    <button data-on:click="@get('/endpoint', {contentType: 'form'})"></button>
</form>
```

### `@post()`

> `@post(uri: string, options={ })`

Works the same as `@get()` but sends a `POST` request to the backend.

```
<button data-on:click="@post('/endpoint')"></button>
```

### `@put()`

> `@put(uri: string, options={ })`

Works the same as `@get()` but sends a `PUT` request to the backend.

```
<button data-on:click="@put('/endpoint')"></button>
```

### `@patch()`

> `@patch(uri: string, options={ })`

Works the same as `@get()` but sends a `PATCH` request to the backend.

```
<button data-on:click="@patch('/endpoint')"></button>
```

### `@delete()`

> `@delete(uri: string, options={ })`

Works the same as `@get()` but sends a `DELETE` request to the backend.

```
<button data-on:click="@delete('/endpoint')"></button>
```

### Options

All of the actions above take a second argument of options.

- `contentType` – The type of content to send. A value of `json` sends all signals in a JSON request. A value of `form` tells the action to look for the closest form to the element on which it is placed (unless a `selector` option is provided), perform validation on the form elements, and send them to the backend using a form request (no signals are sent). Defaults to `json`.
- `filterSignals` – A filter object with an `include` property that accepts a regular expression to match signal paths (defaults to all signals: `/.*/`), and an optional `exclude` property to exclude specific signal paths (defaults to all signals that do not have a `_` prefix: `/(^_|\._).*/`).
  
  > The Datastar Inspector can be used to inspect and filter current signals and view signal patch events in real-time.
- `selector` – Optionally specifies a form to send when the `contentType` option is set to `form`. If the value is `null`, the closest form is used. Defaults to `null`.
- `headers` – An object containing headers to send with the request.
- `openWhenHidden` – Whether to keep the connection open when the page is hidden. Useful for dashboards but can cause a drain on battery life and other resources when enabled. Defaults to `false`.
- `retryInterval` – The retry interval in milliseconds. Defaults to `1000` (one second).
- `retryScaler` – A numeric multiplier applied to scale retry wait times. Defaults to `2`.
- `retryMaxWaitMs` – The maximum allowable wait time in milliseconds between retries. Defaults to `30000` (30 seconds).
- `retryMaxCount` – The maximum number of retry attempts. Defaults to `10`.
- `requestCancellation` – Controls request cancellation behavior. Can be `'auto'` (default, cancels existing requests on the same element), `'disabled'` (allows concurrent requests), or an `AbortController` instance for custom control. Defaults to `'auto'`.
- `override` – When `contentType` is `'json'`, sends this object as the request body instead of the default filtered signals. Useful for posting explicit payloads (e.g., optimistic UI updates).
- `responseOverrides` – Overrides how responses are applied on the client. For `text/html`, accepts `{ selector?: string, mode?: 'outer'|'inner'|'remove'|'replace'|'prepend'|'append'|'before'|'after', useViewTransition?: boolean }`. For `application/json`, accepts `{ onlyIfMissing?: boolean }`.

```
<button data-on:click="@get('/endpoint', {
    filterSignals: {include: /^foo\./},
    headers: {
        'X-Csrf-Token': 'JImikTbsoCYQ9oGOcvugov0Awc5LbqFsZW6ObRCxuq',
    },
    openWhenHidden: true,
    requestCancellation: 'disabled',
    // Force HTML fragment into a specific target and mode
    responseOverrides: { selector: '#content', mode: 'inner' },
    // Send a precise JSON body instead of filtered signals
    override: { id: 123, active: true },
})"></button>
```

### Request Cancellation

By default, when a new fetch request is initiated on an element, any existing request on that same element is automatically cancelled. This prevents multiple concurrent requests from conflicting with each other and ensures clean state management.

For example, if a user rapidly clicks a button that triggers a backend action, only the most recent request will be processed:

```
<!-- Clicking this button multiple times will cancel previous requests (default behavior) -->
<button data-on:click="@get('/slow-endpoint')">Load Data</button>
```

This automatic cancellation happens at the element level, meaning requests on different elements can run concurrently without interfering with each other.

You can control this behavior using the `requestCancellation` option:

```
<!-- Allow concurrent requests (no automatic cancellation) -->
<button data-on:click="@get('/endpoint', {requestCancellation: 'disabled'})">Allow Multiple</button>

<!-- Custom abort controller for fine-grained control -->
<div data-signals:controller="new AbortController()">
    <button data-on:click="@get('/endpoint', {requestCancellation: $controller})">Start Request</button>
    <button data-on:click="$controller.abort()">Cancel Request</button>
</div>
```

### Response Handling

Backend actions automatically handle different response content types:

- `text/event-stream` – Standard SSE responses with Datastar SSE events.
- `text/html` – HTML elements to patch into the DOM.
- `application/json` – JSON encoded signals to patch.
- `text/javascript` – JavaScript code to execute in the browser.

#### `text/html`

When returning HTML (`text/html`), the server can optionally include the following response headers:

- `datastar-selector` – A CSS selector for the target elements to patch
- `datastar-mode` – How to patch the elements (`outer`, `inner`, `remove`, `replace`, `prepend`, `append`, `before`, `after`). Defaults to `outer`.
- `datastar-use-view-transition` – Whether to use the View Transition API when patching elements.

```
response.headers.set('Content-Type', 'text/html')
response.headers.set('datastar-selector', '#my-element')
response.headers.set('datastar-mode', 'inner')
response.body = '<p>New content</p>'
```

#### `application/json`

When returning JSON (`application/json`), the server can optionally include the following response header:

- `datastar-only-if-missing` – If set to `true`, only patch signals that don’t already exist.

```
response.headers.set('Content-Type', 'application/json')
response.headers.set('datastar-only-if-missing', 'true')
response.body = JSON.stringify({ foo: 'bar' })
```

#### `text/javascript`

When returning JavaScript (`text/javascript`), the server can optionally include the following response header:

- `datastar-script-attributes` – Sets the script element’s attributes using a JSON encoded string.

```
response.headers.set('Content-Type', 'text/javascript')
response.headers.set('datastar-script-attributes', JSON.stringify({ type: 'module' }))
response.body = 'console.log("Hello from server!");'
```

### Events

All of the actions above trigger `datastar-fetch` events during the fetch request lifecycle. The event type determines the stage of the request.

- `started` – Triggered when the fetch request is started.
- `finished` – Triggered when the fetch request is finished.
- `error` – Triggered when the fetch request encounters an error.
- `retrying` – Triggered when the fetch request is retrying.
- `retries-failed` – Triggered when all fetch retries have failed.

```
<div data-on:datastar-fetch="
    evt.detail.type === 'error' && console.log('Fetch error encountered')
"></div>
```

## Pro Actions

### `@clipboard()` Pro

> `@clipboard(text: string, isBase64?: boolean)`

Copies the provided text to the clipboard. If the second parameter is `true`, the text is treated as Base64 encoded, and is decoded before copying.

> Base64 encoding is useful when copying content that contains special characters, quotes, or code fragments that might not be valid within HTML attributes. This prevents parsing errors and ensures the content is safely embedded in `data-*` attributes.

```
<!-- Copy plain text -->
<button data-on:click="@clipboard('Hello, world!')"></button>

<!-- Copy base64 encoded text (will decode before copying) -->
<button data-on:click="@clipboard('SGVsbG8sIHdvcmxkIQ==', true)"></button>
```

### `@fit()` Pro

> `@fit(v: number, oldMin: number, oldMax: number, newMin: number, newMax: number, shouldClamp=false, shouldRound=false)`

Linearly interpolates a value from one range to another. This is useful for converting between different scales, such as mapping a slider value to a percentage or converting temperature units.

The optional `shouldClamp` parameter ensures the result stays within the new range, and `shouldRound` rounds the result to the nearest integer.

```
<!-- Convert a 0-100 slider to 0-255 RGB value -->
<div>
    <input type="range" min="0" max="100" value="50" data-bind:slider-value>
    <div data-computed:rgb-value="@fit($sliderValue, 0, 100, 0, 255)">
        RGB Value: <span data-text="$rgbValue"></span>
    </div>
</div>

<!-- Convert Celsius to Fahrenheit -->
<div>
    <input type="number" data-bind:celsius value="20" />
    <div data-computed:fahrenheit="@fit($celsius, 0, 100, 32, 212)">
        <span data-text="$celsius"></span>°C = <span data-text="$fahrenheit.toFixed(1)"></span>°F
    </div>
</div>

<!-- Map mouse position to element opacity (clamped) -->
<div
    data-signals:mouse-x="0"
    data-computed:opacity="@fit($mouseX, 0, window.innerWidth, 0, 1, true)"
    data-on:mousemove__window="$mouseX = evt.clientX"
    data-attr:style="'opacity: ' + $opacity"
>
    Move your mouse horizontally to change opacity
</div>
```

# Rocket

Rocket is currently in alpha – available with Datastar Pro.

Rocket is a Datastar Pro plugin that bridges Web Components with Datastar’s reactive system. It allows you to create encapsulated, reusable components with reactive data binding.

> Rocket is a powerful feature, and should be used sparingly. For most applications, standard Datastar templates and global signals are sufficient. Reserve Rocket for cases where component encapsulation is essential, such as integrating third-party libraries or creating complex, reusable UI elements.

### Basic example

Traditional web components require verbose class definitions and manual DOM management. Rocket eliminates this complexity with a declarative, template-based approach.

Here’s a Rocket component compared to a vanilla web component.

![](https://data-star.dev/cdn-cgi/image/format=auto/static/images/rocket-128x128-38eb37d4251e4854ef5fdd7bbee042336c82e36fa2fbafdd212d911c74c7fd39.png)

```
<template data-rocket:simple-counter
          data-props:count="int|min:0|=0"
          data-props:start="int|min:0|=0"
          data-props:step="int|min:1|max:10|=1"
>
  <script>
    $$count = $$start
  </script>
  <div data-if="$$errs?.start" data-text="$$errs.start[0].value"></div>
  <div data-if="$$errs?.step" data-text="$$errs.step[0].value"></div>
  <button data-on:click="$$count -= $$step">-</button>
  <span data-text="$$count"></span>
  <button data-on:click="$$count += $$step">+</button>
  <button data-on:click="$$count = $$start">Reset</button>
</template>
```

```
class SimpleCounter extends HTMLElement {
  static observedAttributes = ['start', 'step'];
  
  constructor() {
    super();
    this.innerHTML = `
      <div class="error" style="display: none;"></div>
      <button class="dec">-</button>
      <span class="count">0</span>
      <button class="inc">+</button>
      <button class="reset">Reset</button>
    `;
    
    this.errorEl = this.querySelector('.error');
    this.decBtn = this.querySelector('.dec');
    this.incBtn = this.querySelector('.inc');
    this.resetBtn = this.querySelector('.reset');
    this.countEl = this.querySelector('.count');
    
    this.handleDec = () => { 
      const newValue = this.count - this.step;
      if (newValue >= 0) {
        this.count = newValue;
        this.updateDisplay();
      }
    };
    this.handleInc = () => { 
      this.count += this.step;
      this.updateDisplay();
    };
    this.handleReset = () => { 
      this.count = this.start; 
      this.updateDisplay(); 
    };
    
    this.decBtn.addEventListener('click', this.handleDec);
    this.incBtn.addEventListener('click', this.handleInc);
    this.resetBtn.addEventListener('click', this.handleReset);
  }
  
  connectedCallback() {
    const startVal = parseInt(this.getAttribute('start') || '0');
    const stepVal = parseInt(this.getAttribute('step') || '1');
    
    if (startVal < 0) {
      this.errorEl.textContent = 'start must be at least 0';
      this.errorEl.style.display = 'block';
      this.start = 0;
    } else {
      this.start = startVal;
      this.errorEl.style.display = 'none';
    }
    
    if (stepVal < 1 || stepVal > 10) {
      this.errorEl.textContent = 'step must be between 1 and 10';
      this.errorEl.style.display = 'block';
      this.step = Math.max(1, Math.min(10, stepVal));
    } else {
      this.step = stepVal;
      if (this.start === startVal) {
        this.errorEl.style.display = 'none';
      }
    }
    
    this.count = this.start;
    this.updateDisplay();
  }
  
  disconnectedCallback() {
    this.decBtn.removeEventListener('click', this.handleDec);
    this.incBtn.removeEventListener('click', this.handleInc);
    this.resetBtn.removeEventListener('click', this.handleReset);
  }
  
  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'start') {
      const startVal = parseInt(newValue || '0');
      if (startVal < 0) {
        this.errorEl.textContent = 'start must be at least 0';
        this.errorEl.style.display = 'block';
        this.start = 0;
      } else {
        this.start = startVal;
        this.errorEl.style.display = 'none';
      }
      this.count = this.start;
    } else if (name === 'step') {
      const stepVal = parseInt(newValue || '1');
      if (stepVal < 1 || stepVal > 10) {
        this.errorEl.textContent = 'step must be between 1 and 10';
        this.errorEl.style.display = 'block';
        this.step = Math.max(1, Math.min(10, stepVal));
      } else {
        this.step = stepVal;
        this.errorEl.style.display = 'none';
      }
    }
    if (this.isConnected) {
      this.updateDisplay();
    }
  }
  
  updateDisplay() {
    this.countEl.textContent = this.count;
  }
}

customElements.define('simple-counter', SimpleCounter);
```

## Overview

Rocket allows you to turn HTML templates into fully reactive web components. The backend remains the source of truth, but your frontend components are now encapsulated and reusable without any of the usual hassle.

Add `data-rocket:my-component` to a `template` element to turn it into a Rocket component. Component signals are automatically scoped with `$$`, so component instances don’t interfere with each other.

You can use Rocket to wrap external libraries using module imports, and create references to elements within your component. Each component gets its own signal namespace that plays nicely with Datastar’s global signals. When you remove a component from the DOM, all its `$$` signals are cleaned up automatically.

### Bridging Web Components and Datastar

Web components want encapsulation; Datastar wants a global signal store. Rocket gives you both by creating isolated namespaces for each component. Each instance gets its own sandbox that doesn’t mess with other components on the page, or with global signals.

Multiple component instances work seamlessly, each getting its own numbered namespace. You still have access to global signals when you need them, but your component state stays isolated and clean.

### Signal Scoping

Use `$$` for component-scoped signals, and `$` for global signals. Component signals are automatically cleaned up when you remove the component from the DOM - no memory leaks, no manual cleanup required.

Behind the scenes, your `$$count` becomes something like `$._rocket.my_counter._1.count`, with each instance getting its own numbered namespace. You never have to think about this complexity - just write `$$count` and Rocket handles the rest.

```
// Your component template writes:
<button data-on:click="$$count++">Increment</button>
<span data-text="$$count"></span>

// Rocket transforms it to (for instance #1):
<button data-on:click="$._rocket.my_counter._1.count++">Increment</button>
<span data-text="$._rocket.my_counter._1.count"></span>

// The global Datastar signal structure:
$._rocket = {
  my_counter: {
    _1: { count: 0 }, // First counter instance
    _2: { count: 5 }, // Second counter instance
    _3: { count: 10 } // Third counter instance
  },
  user_card: {
    _4: { name: "Alice" }, // Different component type
    _5: { name: "Bob" }
  }
}
```

## Defining Rocket Components

Rocket components are defined using a HTML `template` element with the `data-rocket:my-component` attribute, where `my-component` is the name of the resulting web component. The name must contain at least one hyphen, as per the custom element specification.

```
<template data-rocket:my-counter>
  <script>
    $$count = 0  
  </script>
  <button data-on:click="$$count++">
    Count: <span data-text="$$count"></span>
  </button>
</template>
```

This gets compiled to a web component, meaning that usage is simply:

```
<my-counter></my-counter>
```

## Signal Management

Rocket makes it possible to work with both component-scoped and global signals (global to the entire page).

### Component Signals

Component-scoped signals use the `$$` prefix and are isolated to each component instance.

```
<template data-rocket:isolated-counter>
  <script>
    // These are component-scoped – each instance has its own values
    $$count = 0
    $$step = 1
    $$maxCount = 10
    $$isAtMax = computed(() => $$count >= $$maxCount)
    
    // Component actions
    actions.increment = () => {
      if ($$count < $$maxCount) {
        $$count += $$step
      }
    }
  </script>
  
  <div>
    <p>Count: <span data-text="$$count"></span></p>
    <p data-show="$$isAtMax" class="error">Maximum reached!</p>
    <button data-on:click="@increment()" data-attr:disabled="$$isAtMax">+</button>
  </div>
</template>

<!-- Multiple instances work independently -->
<isolated-counter></isolated-counter>
<isolated-counter></isolated-counter>
```

### Global Signals

Global signals use the `$` prefix and are shared across the entire page.

```
<template data-rocket:theme-toggle>
  <script>
    // Access global theme state
    if (!$theme) {
      $theme = 'light'
    }
    
    actions.toggleTheme = () => {
      $theme = $theme === 'light' ? 'dark' : 'light'
    }
  </script>
  
  <button data-on:click="@toggleTheme()">
    <span data-text="$theme === 'light' ? '🌙' : '☀️'"></span>
    <span data-text="$theme === 'light' ? 'Dark Mode' : 'Light Mode'"></span>
  </button>
</template>

<!-- All instances share the same global theme -->
<theme-toggle></theme-toggle>
<theme-toggle></theme-toggle>
```

## Props

The `data-props:*` attribute allows you to define component props with codecs for validation and defaults.

```
<!-- Component definition with defaults -->
<template data-rocket:progress-bar
          data-props:value="int|=0"
          data-props:max="int|=100" 
          data-props:color="string|=blue"
>
  <script>
    $$percentage = computed(() => Math.round(($$value / $$max) * 100))
  </script>
  
  <div class="progress-container">
    <div class="progress-bar" 
        data-style="{
          width: $$percentage + '%',
          backgroundColor: $$color
        }">
    </div>
    <span data-text="$$percentage + '%'"></span>
  </div>
</template>

<!-- Usage -->
<progress-bar data-attr:value="'75'" data-attr:color="'green'"></progress-bar>
<progress-bar data-attr:value="'30'" data-attr:max="'50'"></progress-bar>
```

Rocket automatically transforms and validates values using the codecs defined in `data-props:*` attributes.

## Setup Scripts

Setup scripts initialize component behavior and run when the component is created. Rocket supports both component (per-instance) and static (one-time) setup scripts.

### Component Setup Scripts

Regular `<script>` tags run for each component instance.

```
<template data-rocket:timer
          data-props:seconds="int|=0"
          data-props:running="boolean|=false"
          data-props:interval="int|=1000"
>
  <script>
    $$minutes = computed(() => Math.floor($$seconds / 60))
    $$displayTime = computed(() => {
      const m = String($$minutes).padStart(2, '0')
      const s = String($$seconds % 60).padStart(2, '0')
      return m + ':' + s
    })
    
    let intervalId
    effect(() => {
      if ($$running) {
        intervalId = setInterval(() => $$seconds++, $$interval)
      } else {
        clearInterval(intervalId)
      }
    })
    
    // Cleanup when component is removed
    onCleanup(() => {
      clearInterval(intervalId)
    })
  </script>
  
  <div>
    <h2 data-text="$$displayTime"></h2>
    <button data-on:click="$$running = !$$running" 
            data-text="$$running ? 'Stop' : 'Start'">
    </button>
    <button data-on:click="$$seconds = 0">Reset</button>
</div>
</template>
```

### Static Setup Scripts

Scripts with a `data-static` attribute only run once, when the component type is first registered. This is useful for shared constants or utilities.

```
<template data-rocket:icon-button>
  <script data-static>
    const icons = {
      heart: '❤️',
      star: '⭐',
      thumbs: '👍',
      fire: '🔥'
    }
  </script>
  
  <script>
    $$icon = $$type || 'heart'
    $$emoji = computed(() => icons[$$icon] || '❓')
  </script>
  
  <button data-on:click="@click()">
    <span data-text="$$emoji"></span>
    <span data-text="$$label || 'Click me'"></span>
  </button>
</template>
```

## Module Imports

Rocket allows you to wrap external libraries, loading them before the component initializes and the setup script runs. Use `data-import-esm:*` for modern ES modules and `data-import-iife:*` for legacy global libraries.

### ESM Imports

The `data-import-esm:*` attribute should be used for modern ES modules.

```
<template data-rocket:qr-generator
          data-props:text="string|trim|required!|=Hello World"
          data-props:size="int|min:50|max:1000|=200"
          data-import:esm-qr="https://cdn.jsdelivr.net/npm/[email protected]/+esm"
>
  <script>
    $$errorText = ''
    
    effect(() => {
      // Check for validation errors first
      if ($$hasErrs) {
        const messages = []
        if ($$errs?.text) {
          messages.push('Text is required')
        }
        if ($$errs?.size) {
          messages.push('Size must be 50-1000px')
        }
        $$errorText = messages.join(', ') || 'Validation failed'
        return
      }

      if (!$$canvas) {
        return
      }

      if (!qr) {
        $$errorText = 'QR library not loaded'
        return
      }
      
      try {
        qr.render({
          text: $$text,
          size: $$size
        }, $$canvas)
        $$errorText = ''
      } catch (err) {
        $$errorText = 'QR generation failed'
      }
    })
  </script>
  
  <div data-style="{width: $$size + 'px', height: $$size + 'px'}">
    <canvas data-if="!$$errorText" data-ref="canvas" style="display: block;"></canvas>
    <div data-else data-text="$$errorText" class="error"></div>
  </div>
</template>
```

### IIFE Imports

The `data-import-iife:*` attribute should be used for legacy libraries. The library must expose a global variable that matches the alias you specify after `data-import-iife:`.

```
<template data-rocket:chart
          data-props:data="json|=[]"
          data-props:type="string|=line"
          data-import-iife:chart="https://cdn.jsdelivr.net/npm/[email protected]/dist/chart.umd.js"
>
  <script>
    let chartInstance
    
    effect(() => {
      if (!$$canvas || !chart || !$$data.length) {
        return
      }

      if (chartInstance) {
        chartInstance.destroy()
      }
      
      const ctx = $$canvas.getContext('2d')
      chartInstance = new chart.Chart(ctx, {
        type: $$type,
        data: {
          datasets: [{
            data: $$data,
            backgroundColor: '#3b82f6'
          }]
        }
      })
    })
    
    onCleanup(() => {
      if (chartInstance) {
        chartInstance.destroy()
      }
    })
  </script>
  
  <canvas data-ref="canvas"></canvas>
</template>
```

## Rocket Attributes

In addition to the Rocket-specific `data-*` attributes defined above, the following attributes are available within Rocket components.

### `data-if`

Conditionally outputs an element based on an expression.

```
<div data-if="$$items.count" 
     data-text="$$items.count + ' items'">
></div>
```

### `data-else-if`

Conditionally outputs an element based on an expression, if the preceding `data-if` condition is falsy.

```
<div data-if="$$items.count" 
     data-text="$$items.count + ' items found.'">
></div>
<div data-else-if="$$items.count == 1"
     data-text="$$items.count + ' item found.'">
></div>
```

### `data-else`

Outputs an element if the preceding `data-if` and `data-else-if` conditions are falsy.

```
<div data-if="$$items.count" 
     data-text="$$items.count + ' items found.'">
></div>
<div data-else>No items found.</div>
```

### `data-for`

Loops over any iterable (arrays, maps, sets, strings, and plain objects), and outputs the element for each item.

```
<div data-for="item, index in $$items">
  <span data-text="index + ': ' + item.name"></span>
</div>
```

The first alias (`item` above) is available to descendants just like any other binding. An optional second alias (`index` above) exposes the current key or numeric index. Nested loops are supported, and inner loop variables automatically shadow outer ones, so you can reuse names without conflicts.

```
<div data-for="items in $$itemSet">
  <div data-for="item in items">
    <span data-text="item.name"></span>
  </div>
</div>
```

## Reactive Patterns

Rocket provides `computed` and `effect` functions for declarative reactivity. These keep your component state automatically in sync with the DOM.

### Computed Values

Computed values automatically update when their dependencies change.

```
<template data-rocket:shopping-cart
          data-props:items="json|=[]"
>
  <script>
    // Computed values automatically recalculate
    $$total = computed(() => 
      $$items.reduce((sum, item) => sum + (item.price * item.quantity), 0)
    )
    
    $$itemCount = computed(() =>
      $$items.reduce((sum, item) => sum + item.quantity, 0)
    )
    
    $$isEmpty = computed(() => $$items.length === 0)
    
    // Actions that modify reactive state
    actions.addItem = (item) => {
      $$items = [...$$items, { ...item, quantity: 1 }]
    }
    
    actions.removeItem = (index) => {
      $$items = $$items.filter((_, i) => i !== index)
    }
  </script>
  
  <div>
    <h3>Shopping Cart</h3>
    <p data-show="$$isEmpty">Cart is empty</p>
    <p data-show="!$$isEmpty">
      Items: <span data-text="$$itemCount"></span> | 
      Total: $<span data-text="$$total.toFixed(2)"></span>
    </p>
    
    <div data-for="item, index in $$items">
      <span data-text="item.name"></span> - 
      <span data-text="'$' + item.price"></span>
      <button data-on:click="@removeItem(index)">Remove</button>
    </div>
  </div>
</template>
```

### Effects and Watchers

Effects run side effects when reactive values change.

```
<template data-rocket:auto-saver
          data-props:data="string|="
          data-props:last-saved="string|="
          data-props:saving="boolean|=false"
>
  <script>
    let saveTimeout
    
    // Auto-save effect
    effect(() => {
      if (!$$data) {
        return
      }
      
      clearTimeout(saveTimeout)
      saveTimeout = setTimeout(async () => {
        $$saving = true
        try {
          await actions.post('/api/save', { data: $$data })
          $$lastSaved = new Date().toLocaleTimeString()
        } catch (error) {
          console.error('Save failed:', error)
        } finally {
          $$saving = false
        }
      }, 1000) // Debounce by 1 second
    })
    
    // Theme effect
    effect(() => {
      if ($theme) {
        document.body.className = $theme + '-theme'
      }
    })
    
    onCleanup(() => {
      clearTimeout(saveTimeout)
    })
  </script>
  
  <div>
    <textarea data-bind="data" placeholder="Start typing..."></textarea>
    <p data-show="$$saving">Saving...</p>
    <p data-show="$$lastSaved">Last saved: <span data-text="$$lastSaved"></span></p>
  </div>
</template>
```

## Element References

You can use `data-ref` to create references to elements within your component. Element references are available as `$$elementName` signals and automatically updated when the DOM changes.

```
<template data-rocket:canvas-painter
          data-props:color="string|=#000000"
          data-props:brush-size="int|=5"
>
  <script>
    let ctx
    let isDrawing = false
    
    // Get canvas context when canvas is available
    effect(() => {
      if ($$canvas) {
        ctx = $$canvas.getContext('2d')
        ctx.strokeStyle = $$color
        ctx.lineWidth = $$brushSize
        ctx.lineCap = 'round'
      }
    })
    
    // Update drawing properties
    effect(() => {
      if (ctx) {
        ctx.strokeStyle = $$color
        ctx.lineWidth = $$brushSize
      }
    })
    
    actions.startDrawing = (e) => {
      isDrawing = true
      const rect = $$canvas.getBoundingClientRect()
      ctx.beginPath()
      ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top)
    }
    
    actions.draw = (e) => {
      if (!isDrawing) {
        return
      }

      const rect = $$canvas.getBoundingClientRect()
      ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top)
      ctx.stroke()
    }
    
    actions.stopDrawing = () => {
      isDrawing = false
    }
    
    actions.clear = () => {
      if (ctx) {
        ctx.clearRect(0, 0, $$canvas.width, $$canvas.height)
      }
    }
  </script>
  
  <div>
    <div>
      <label>Color: <input type="color" data-bind="color"></label>
      <label>Size: <input type="range" min="1" max="20" data-bind="brushSize"></label>
      <button data-on:click="@clear()">Clear</button>
    </div>
    
    <canvas 
      data-ref="canvas" 
      width="400" 
      height="300"
      style="border: 1px solid #ccc"
      data-on:mousedown="@startDrawing"
      data-on:mousemove="@draw"
      data-on:mouseup="@stopDrawing"
      data-on:mouseleave="@stopDrawing">
    </canvas>
  </div>
</template>
```

## Validation with Codecs

Rocket’s built-in codec system makes it possible to validate user input. By defining validation rules directly in your `data-props:*` attributes, data is automatically transformed and validated as it flows through your component.

### Type Codecs

Type codecs convert and validate prop values.

```
<template data-rocket:validated-form
          data-props:email="string|trim|required!|="
          data-props:age="int|min:18|max:120|=0"
          data-props:score="int|clamp:0,100|=0"
>
  <script>
    // Signals are automatically validated by the codec system
    // No need for manual codec setup - just use the signals directly
    
    // Check for validation errors using the built-in $$hasErrs signal
    // No need to create computed - $$hasErrs is automatically available
  </script>
  
  <form>
    <div>
      <label>Email (required):</label>
      <input type="email" data-bind="email">
      <span data-show="$$errs?.email" class="error">Email is required</span>
    </div>
    
    <div>
      <label>Age (18-120):</label>
      <input type="number" data-bind="age">
      <span data-show="$$errs?.age" class="error">Age must be 18-120</span>
    </div>
    
    <div>
      <label>Score (0-100, auto-clamped):</label>
      <input type="number" data-bind="score">
      <span>Current: <span data-text="$$score"></span></span>
    </div>
    
    <button type="submit" data-attr:disabled="$$hasErrors">
      Submit
    </button>
  </form>
</template>
```

### Validation Rules

Codecs can either **transform** values (modify them) or **validate** them (check them without modifying). Use the `!` suffix to make any codec validation-only.

- `min:10` - Transform: clamps value to minimum 10
- `min:10!` - Validate: rejects values below 10, keeps original on failure
- `trim` - Transform: removes whitespace
- `trim!` - Validate: rejects untrimmed strings

CodecTransformValidation **Type Conversion**`string`Converts to stringIs string?`int`Converts to integerIs integer?`float`Converts to numberIs numeric?`date`Converts ISO strings or timestamps to a `Date` objectIs valid date?`bool`Converts to booleanIs boolean?`json`Parses JSON stringValid JSON?`js`Parses JS object literal  
**⚠️ Avoid client values**Valid JS syntax?`binary`Decodes base64Valid base64?**Validation**`required`-Not empty?`oneOf:a,b,c`Defaults to first option if invalidIs valid option?**Numeric Constraints**`min:n`Clamp to minimum value&gt;= minimum?`max:n`Clamp to maximum value&lt;= maximum?`clamp:min,max`Clamp between min and maxIn range?`round` / `round:n`Round to n decimal placesIs rounded?`ceil:n` / `floor:n`Ceiling/floor to n decimal placesIs ceiling/floor?**String Transforms**`trim`Remove leading/trailing whitespace-`upper` / `lower`Convert to upper/lowercase-`kebab` / `camel`Convert case styleCorrect case?`snake` / `pascal`Convert case styleCorrect case?`title` / `title:first`Title case (all words or first only)-**String Constraints**`minLength:n`-Length &gt;= n?`maxLength:n`Truncates if too longLength &lt;= n?`length:n`-Length equals n?`regex:pattern`-Matches regex?`startsWith:text`Adds prefix if missingStarts with text?`endsWith:text`Adds suffix if missingEnds with text?`includes:text`-Contains text?**Advanced Numeric**`lerp:min,max`Linear interpolation (0-1 to min-max)-`fit:in1,in2,out1,out2`Map value from one range to another-

## Component Lifecycle

Rocket components have a simple lifecycle with automatic cleanup.

```
<template data-rocket:lifecycle-demo>
  <script>
    console.log('Component initializing...')
    
    $$mounted = true
    
    // Setup effects and timers
    const intervalId = setInterval(() => {
      console.log('Component is alive')
    }, 5000)
    
    // Cleanup when component is removed from DOM
    onCleanup(() => {
      console.log('Component cleanup')
      clearInterval(intervalId)
      $$mounted = false
    })
  </script>
  
  <div>
    <p data-show="$$mounted">Component is mounted</p>
  </div>
</template>
```

The lifecycle is as follows:

1. Rocket processes your template and registers the component.
2. When you add it to the DOM, the instance is created and setup scripts run to initialize your signals.
3. The component becomes reactive and responds to data changes.
4. When you remove it from the DOM, all `onCleanup` callbacks run automatically.

## Optimistic UI

Rocket pairs seamlessly with Datastar’s server-driven model to provide instant visual feedback without shifting ownership of state to the browser. In the Rocket flow example, dragging a node instantly renders its optimistic position in the SVG while the original light-DOM host remains hidden. The component adds an `.is-pending` class to dim the node and connected edges, signaling that the drag is provisional. Once the backend confirms the new coordinates and updates the layout, the component automatically clears the pending style.

A dedicated prop such as `server-update-time="date|=…"` makes this straightforward: each tab receives an updated timestamp from the server (via SSE or a patch), Rocket decodes it into a `Date`, and internal effects react to reconcile every view. Unlike client-owned graph editors (e.g. React Flow), the server stays the single source of truth, while the optimistic UI remains a thin layer inside the component.

## Examples

Check out the Copy Button as a basic example, the QR Code generator with validation, the ECharts integration for data visualization, the interactive 3D Globe with markers, and the Virtual Scroll example for handling large datasets efficiently.

# SSE Events

Responses to backend actions with a content type of `text/event-stream` can contain zero or more Datastar SSE events.

> The backend SDKs can handle the formatting of SSE events for you, or you can format them yourself.

## Event Types

### `datastar-patch-elements`

Patches one or more elements in the DOM. By default, Datastar morphs elements by matching top-level elements based on their ID.

```
event: datastar-patch-elements
data: elements <div id="foo">Hello world!</div>

```

In the example above, the element `<div id="foo">Hello world!</div>` will be morphed into the target element with ID `foo`.

> Be sure to place IDs on top-level elements to be morphed, as well as on elements within them that you’d like to preserve state on (event listeners, CSS transitions, etc.).

SVG morphing in Datastar requires special handling due to XML namespaces. See the SVG morphing example.

Additional `data` lines can be added to the response to override the default behavior.

KeyDescription `data: mode outer`Morphs the outer HTML of the elements. This is the default (and recommended) mode.`data: mode inner`Morphs the inner HTML of the elements.`data: mode replace`Replaces the outer HTML of the elements.`data: mode prepend`Prepends the elements to the target’s children.`data: mode append`Appends the elements to the target’s children.`data: mode before`Inserts the elements before the target as siblings.`data: mode after`Inserts the elements after the target as siblings.`data: mode remove`Removes the target elements from DOM.`data: selector #foo`Selects the target element of the patch using a CSS selector. Not required when using the `outer` or `replace` modes.`data: useViewTransition true`Whether to use view transitions when patching elements. Defaults to `false`.`data: elements`The HTML elements to patch.

```
event: datastar-patch-elements
data: elements <div id="foo">Hello world!</div>

```

Elements can be removed using the `remove` mode and providing a `selector`.

```
event: datastar-patch-elements
data: mode remove
data: selector #foo

```

Elements can span multiple lines. Sample output showing non-default options:

```
event: datastar-patch-elements
data: mode inner
data: selector #foo
data: useViewTransition true
data: elements <div>
data: elements        Hello world!
data: elements </div>

```

### `datastar-patch-signals`

Patches signals into the existing signals on the page. The `onlyIfMissing` line determines whether to update each signal with the new value only if a signal with that name does not yet exist. The `signals` line should be a valid `data-signals` attribute.

```
event: datastar-patch-signals
data: signals {foo: 1, bar: 2}

```

Signals can be removed by setting their values to `null`.

```
event: datastar-patch-signals
data: signals {foo: null, bar: null}

```

Sample output showing non-default options:

```
event: datastar-patch-signals
data: onlyIfMissing true
data: signals {foo: 1, bar: 2}

```

# SDKs

Datastar provides backend SDKs that can (optionally) simplify the process of generating SSE events specific to Datastar.

> If you’d like to contribute an SDK, please follow the Contribution Guidelines.

## Clojure

A Clojure SDK as well as helper libraries and adapter implementations.

*Maintainer: Jeremy Schoffen*

Clojure SDK &amp; examples

## C\#

A C# (.NET) SDK for working with Datastar.

*Maintainer: Greg H*  
*Contributors: Ryan Riley*

C# (.NET) SDK &amp; examples

## Go

A Go SDK for working with Datastar.

*Maintainer: Delaney Gillilan*

*Other examples: 1 App 5 Stacks ported to Go+Templ+Datastar*

Go SDK &amp; examples

## Java

A Java SDK for working with Datastar.

*Maintainer: mailq*  
*Contributors: Peter Humulock, Tom D.*

Java SDK &amp; examples

## Kotlin

A Kotlin SDK for working with Datastar.

*Maintainer: GuillaumeTaffin*

Kotlin SDK &amp; examples

## PHP

A PHP SDK for working with Datastar.

*Maintainer: Ben Croker*

PHP SDK &amp; examples

### Craft CMS

Integrates the Datastar framework with Craft CMS, allowing you to create reactive frontends driven by Twig templates (by PutYourLightsOn).

Craft CMS plugin

Datastar &amp; Craft CMS demos

### Laravel

Integrates the Datastar hypermedia framework with Laravel, allowing you to create reactive frontends driven by Blade views or controllers (by PutYourLightsOn).

Laravel package

## Python

A Python SDK and a PyPI package (including support for most popular frameworks).

*Maintainer: Felix Ingram*  
*Contributors: Chase Sterling*

Python SDK &amp; examples

## Ruby

A Ruby SDK for working with Datastar.

*Maintainer: Ismael Celis*

Ruby SDK &amp; examples

## Rust

A Rust SDK for working with Datastar.

*Maintainer: Glen De Cauwsemaecker*  
*Contributors: Johnathan Stevers*

Rust SDK &amp; examples

### Rama

Integrates Datastar with Rama, a Rust-based HTTP proxy (example).

Rama module

## TypeScript

A TypeScript SDK with support for Node.js, Deno, and Bun.

*Maintainer: Edu Wass*  
*Contributors: Patrick Marchand*

TypeScript SDK &amp; examples

### PocketPages

Integrates the Datastar framework with PocketPages.

PocketPages plugin

# Security

Datastar expressions are strings that are evaluated in a sandboxed context. This means you can use JavaScript in Datastar expressions.

## Escape User Input

The golden rule of security is to never trust user input. This is especially true when using Datastar expressions, which can execute arbitrary JavaScript. When using Datastar expressions, you should always escape user input. This helps prevent, among other issues, Cross-Site Scripting (XSS) attacks.

## Avoid Sensitive Data

Keep in mind that signal values are visible in the source code in plain text, and can be modified by the user before being sent in requests. For this reason, you should avoid leaking sensitive data in signals and always implement backend validation.

## Ignore Unsafe Input

If, for some reason, you cannot escape unsafe user input, you should ignore it using the `data-ignore` attribute. This tells Datastar to ignore an element and its descendants when processing DOM nodes.

## Content Security Policy

When using a Content Security Policy (CSP), `unsafe-eval` must be allowed for scripts, since Datastar evaluates expressions using a `Function()` constructor.

```
<meta http-equiv="Content-Security-Policy" 
    content="script-src 'self' 'unsafe-eval';"
>
```
