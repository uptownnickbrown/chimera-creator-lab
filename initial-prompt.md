 Please read the project brief in /Users/nbrown/Desktop/chimera-creator/Chimera_Creator_Design_Vision_Spec.md . We
  are building a game called Chimera Creator. You can see art direction screenshots in
  /Users/nbrown/Desktop/chimera-creator/art-direction which I am a big fan of. You can see some other examples
  chimeras, inputs and stats in /Users/nbrown/Desktop/chimera-creator/example-chimeras . The core game loop will
  require AI to execute effectively. I have given you both a Gemini and an OpenAI API key - we may need to evaluate
  which service and model tier to use to do a good enough job. My bias is likely OpenAI these days. But you never
  know. Please look at /Users/nbrown/Desktop/agora - I will use a very similar tech stack here. Python backend,
  Dockerized, deploy on Railway, SQL DB, etc. Note that Agora includes a very strong asset pipeline which you may want
  to reuse here - it defined a style, a list of assets it needed and then generated all ahead of time which allowed
  us to have a very AAA feel instead of building with just HTML and CSS. However, remember that pregeneration is a
  great idea for game assets, but we will need to be able to generate chimeras in a realtime loop in the game so will
  have a runtime AI dependency. Do not worry about cost for now - worry about quality (though speed is an issue if it
  gets too slow to be fun). This will be a one player game and I don't know if that is stated well enough in the
  design spec - I am building this for my son to have a lot of fun on his own, I don't care about multiplayer, don't
  need to worry about cost of lots of kids playing all at once, it is an audience of one for now. But I do want it to
  be a brag-worthy, incredible, fun, creative, magical experience so I do have a high bar for our application quality.
  You will want to build a system where you can dynamically QA your created app and screens and validate it looks as
  AAA quality as you can get it. Ok - begin. Grill me with the user question tool on any questions you have before you
  begin - make sure your goals are aligned with my ideas and intent. They can be game dynamic questions, tech stack
  questions, cost questions, AI integration questions, questions about Agora as a reference game I built, whatever you
  like.