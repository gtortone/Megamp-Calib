// This is a set of JS functions for dealing with the communication
// with the ROOT THttpServer; in particular, this file contains
// functions to figure out what the current set of available histograms is,
// as well as functions to delete the histogram.
// Also include Promisified XHR
// T. Lindner (Jan 2017)


// Promisified XLMHttpRequest wrapper...
// stolen from http://www.html5rocks.com/en/tutorials/es6/promises/
function getUrl(url, postData) {

  if (typeof(postData)==='undefined') postData = false;

  // Return a new promise.
  return new Promise(function(resolve, reject) {

    // Do the usual XHR stuff
    var req = new XMLHttpRequest();

    if(postData != false){
      req.open('POST', url);
    }else{
      req.open('GET', url);
    }


    req.onload = function() {
      // This is called even on 404 etc
      // so check the status
      if (req.status == 200) {
        // Resolve the promise with the response text
        resolve(req.response);
      }
      else {
        // Otherwise reject with the status text
        // which will hopefully be a meaningful error
        reject(req.statusText);
      }
    };

    // Handle network errors
    req.onerror = function() {
      reject("Network Error");
    };

    // Make the request
    if(postData != false){
      req.send(postData);
    }else{
      req.send();
    }
  });
}
